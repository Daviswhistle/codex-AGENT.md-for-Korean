#!/usr/bin/env python3
"""Runtime-enforced Commit-Review-Amend (CRA) gate for Codex.

The gate is intentionally opt-in. A software-engineering agent arms one exact
commit boundary, then the global Codex Stop hook reviews that commit in an
independent ``codex exec review`` thread. Findings are returned as Stop-hook
continuation feedback; a clean review allows the turn to end.

The reviewer process is independent from the parent conversation. This avoids
both accidental parent-history inheritance and coupling CRA correctness to the
current multi-agent implementation.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator, Mapping, MutableMapping, Sequence

SCHEMA_VERSION = 1
MANAGED_HOOK_MARKER = "DAVIS_CRA_HOOK=1"
REVIEWER_GUARD = "DAVIS_CRA_REVIEWER"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "max"
DEFAULT_REVIEW_TIMEOUT_SECONDS = 1_200
DEFAULT_HOOK_TIMEOUT_SECONDS = 1_500
DEFAULT_MAX_REVIEW_FAILURES = 2
DEFAULT_MAX_REASON_CHARS = 14_000
HEARTBEAT_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

JsonObject = dict[str, Any]


class CraError(RuntimeError):
    """Expected CRA configuration, state, or repository error."""


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _parse_timestamp(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _codex_home(explicit: str | None = None) -> Path:
    raw = explicit or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    return Path(raw).expanduser().absolute()


def _state_root(codex_home: Path) -> Path:
    # CODEX_HOME/davis-agent-kit may be a symlink to the source checkout.
    return codex_home / "state" / "davis-agent-kit" / "cra"


def _stable_hash(*parts: str, length: int = 24) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]


def _payload_string(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _context_ids(payload: Mapping[str, Any] | None = None) -> tuple[str | None, str | None]:
    data = payload or {}
    thread_id = (
        os.environ.get("CODEX_THREAD_ID")
        or _payload_string(data, "thread_id", "threadId", "conversation_id")
    )
    session_id = (
        os.environ.get("CODEX_SESSION_ID")
        or _payload_string(data, "session_id", "sessionId")
    )
    return thread_id, session_id


def _identity(payload: Mapping[str, Any] | None = None) -> str:
    thread_id, session_id = _context_ids(payload)
    if thread_id:
        return f"thread:{thread_id}"
    if session_id:
        return f"session:{session_id}"
    return "manual"


def _run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env is not None else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CraError(f"command not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CraError(f"command timed out after {timeout}s: {shlex.join(args)}") from exc

    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        if len(detail) > 2_000:
            detail = detail[-2_000:]
        suffix = f": {detail}" if detail else ""
        raise CraError(f"command failed ({result.returncode}): {shlex.join(args)}{suffix}")
    return result


def _git_root(cwd: Path) -> Path:
    result = _run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(result.stdout.strip()).resolve()


def _git(repo: Path, *args: str, check: bool = True) -> str:
    return _run(["git", *args], cwd=repo, check=check).stdout.strip()


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def _commit_parents(repo: Path, commit: str) -> list[str]:
    fields = _git(repo, "rev-list", "--parents", "-n", "1", commit).split()
    return fields[1:]


def _is_clean(repo: Path) -> bool:
    return not _git(repo, "status", "--porcelain=v1", "--untracked-files=all")


def _ensure_commit(repo: Path, commit: str) -> str:
    return _git(repo, "rev-parse", f"{commit}^{{commit}}")


def _repo_key(repo: Path) -> str:
    return _stable_hash(str(repo.resolve()))


def _state_path(root: Path, repo: Path, identity: str) -> Path:
    return root / "states" / f"{_repo_key(repo)}-{_stable_hash(identity)}.json"


def _active_pointer_path(root: Path, repo: Path) -> Path:
    return root / "active" / f"{_repo_key(repo)}.json"


def _heartbeat_path(root: Path, identity: str) -> Path:
    return root / "heartbeats" / f"{_stable_hash(identity)}.json"


def _lock_path(state_path: Path) -> Path:
    return state_path.with_suffix(state_path.suffix + ".lock")


@contextlib.contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - Windows best effort.
            fcntl = None  # type: ignore[assignment]
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if "fcntl" in locals() and fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _read_json(path: Path) -> JsonObject | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CraError(f"invalid CRA state file: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CraError(f"CRA state must be a JSON object: {path}")
    return value


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def _write_active_pointer(root: Path, repo: Path, state_path: Path, identity: str) -> None:
    _write_json_atomic(
        _active_pointer_path(root, repo),
        {
            "schema_version": SCHEMA_VERSION,
            "repo_root": str(repo),
            "identity": identity,
            "state_path": str(state_path),
            "updated_at": _utc_now(),
        },
    )


def _find_state(
    root: Path,
    repo: Path,
    payload: Mapping[str, Any] | None = None,
) -> tuple[Path, JsonObject] | None:
    identity = _identity(payload)
    exact = _state_path(root, repo, identity)
    state = _read_json(exact)
    if state is not None:
        return exact, state

    manual = _state_path(root, repo, "manual")
    state = _read_json(manual)
    if state is not None:
        return manual, state

    pointer = _read_json(_active_pointer_path(root, repo))
    if not pointer:
        return None
    pointed_identity = pointer.get("identity")
    if identity != "manual" and pointed_identity not in (None, "manual", identity):
        return None
    pointed = pointer.get("state_path")
    if not isinstance(pointed, str):
        return None
    path = Path(pointed)
    state = _read_json(path)
    if state is None or state.get("repo_root") != str(repo):
        return None
    return path, state


def _heartbeat_is_recent(root: Path, payload: Mapping[str, Any] | None = None) -> bool:
    identities: list[str] = [_identity(payload)]
    thread_id, session_id = _context_ids(payload)
    if thread_id:
        identities.append(f"thread:{thread_id}")
    if session_id:
        identities.append(f"session:{session_id}")
    now = dt.datetime.now(dt.timezone.utc)
    for identity in dict.fromkeys(identities):
        heartbeat = _read_json(_heartbeat_path(root, identity))
        if not heartbeat:
            continue
        stamped = _parse_timestamp(heartbeat.get("updated_at"))
        if stamped and (now - stamped).total_seconds() <= HEARTBEAT_MAX_AGE_SECONDS:
            return True
    return False


def _emit_hook(value: Mapping[str, Any]) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _read_hook_payload() -> JsonObject:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CraError(f"hook input is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CraError("hook input must be a JSON object")
    return value


def _payload_cwd(payload: Mapping[str, Any]) -> Path:
    raw = _payload_string(payload, "cwd", "working_directory", "workingDirectory")
    return Path(raw or os.getcwd()).expanduser().absolute()


def _record_heartbeat(payload: Mapping[str, Any], codex_home: Path) -> None:
    root = _state_root(codex_home)
    thread_id, session_id = _context_ids(payload)
    identities = {_identity(payload)}
    if thread_id:
        identities.add(f"thread:{thread_id}")
    if session_id:
        identities.add(f"session:{session_id}")
    body = {
        "schema_version": SCHEMA_VERSION,
        "thread_id": thread_id,
        "session_id": session_id,
        "cwd": str(_payload_cwd(payload)),
        "updated_at": _utc_now(),
    }
    for identity in identities:
        _write_json_atomic(_heartbeat_path(root, identity), body)


def _same_boundary(repo: Path, commit: str, expected_parents: Sequence[str]) -> bool:
    return _commit_parents(repo, commit) == list(expected_parents)


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _parse_review(text: str) -> JsonObject:
    candidate = _strip_json_fence(text)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise CraError(f"reviewer did not return JSON: {exc}") from exc
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as nested:
            raise CraError(f"reviewer returned invalid JSON: {nested}") from nested
    if not isinstance(value, dict):
        raise CraError("reviewer result must be a JSON object")
    findings = value.get("findings")
    correctness = value.get("overall_correctness")
    explanation = value.get("overall_explanation")
    if not isinstance(findings, list):
        raise CraError("reviewer result is missing a findings array")
    if correctness not in {"patch is correct", "patch is incorrect"}:
        raise CraError("reviewer result has an invalid overall_correctness value")
    if not isinstance(explanation, str):
        raise CraError("reviewer result is missing overall_explanation")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise CraError(f"review finding {index + 1} must be an object")
    return value


def _review_command(commit: str, output_path: Path) -> list[str]:
    codex_bin = os.environ.get("DAVIS_CRA_CODEX_BIN", "codex")
    model = os.environ.get("DAVIS_CRA_REVIEW_MODEL", DEFAULT_MODEL)
    effort = os.environ.get("DAVIS_CRA_REVIEW_REASONING_EFFORT", DEFAULT_REASONING_EFFORT)
    return [
        codex_bin,
        "exec",
        "--ephemeral",
        "-c",
        f'model="{model}"',
        "-c",
        f'model_reasoning_effort="{effort}"',
        "--output-last-message",
        str(output_path),
        "review",
        "--commit",
        commit,
    ]


def _tail(text: str, limit: int = 8_000) -> str:
    return text if len(text) <= limit else text[-limit:]


def _run_review(repo: Path, commit: str, root: Path) -> JsonObject:
    reviews = root / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{commit[:12]}-", dir=str(reviews)) as directory:
        output_path = Path(directory) / "last-message.json"
        command = _review_command(commit, output_path)
        child_env: MutableMapping[str, str] = dict(os.environ)
        child_env[REVIEWER_GUARD] = "1"
        child_env.pop("CODEX_THREAD_ID", None)
        child_env.pop("CODEX_SESSION_ID", None)
        timeout = int(
            os.environ.get(
                "DAVIS_CRA_REVIEW_TIMEOUT_SECONDS",
                str(DEFAULT_REVIEW_TIMEOUT_SECONDS),
            )
        )
        result = _run(
            command,
            cwd=repo,
            env=child_env,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            detail = _tail((result.stderr or result.stdout).strip())
            raise CraError(
                f"review command failed with exit {result.returncode}"
                + (f": {detail}" if detail else "")
            )
        raw = (
            output_path.read_text(encoding="utf-8", errors="replace")
            if output_path.exists()
            else result.stdout
        )
        parsed = _parse_review(raw)
        parsed["command"] = command
        parsed["stdout_tail"] = _tail(result.stdout)
        parsed["stderr_tail"] = _tail(result.stderr)
        return parsed


def _finding_summary(finding: Mapping[str, Any], index: int) -> JsonObject:
    result: JsonObject = {
        "index": index,
        "title": str(finding.get("title") or f"Finding {index}"),
        "body": str(finding.get("body") or ""),
    }
    location = finding.get("code_location")
    if isinstance(location, dict):
        result["code_location"] = location
    confidence = finding.get("confidence_score")
    if isinstance(confidence, (int, float)):
        result["confidence_score"] = confidence
    return result


def _findings_reason(state: Mapping[str, Any], commit: str) -> str:
    review = state.get("last_review")
    findings: list[Any] = []
    explanation = ""
    if isinstance(review, dict):
        raw_findings = review.get("findings")
        if isinstance(raw_findings, list):
            findings = raw_findings
        if isinstance(review.get("overall_explanation"), str):
            explanation = review["overall_explanation"]
    summarized = [
        _finding_summary(item, index)
        for index, item in enumerate(findings, start=1)
        if isinstance(item, dict)
    ]
    if not summarized and isinstance(review, dict):
        summarized = [
            {
                "index": 1,
                "title": "Overall review marked the patch incorrect",
                "body": explanation,
            }
        ]
    body = json.dumps(summarized, indent=2, ensure_ascii=False)
    script = Path(__file__).expanduser().absolute()
    reason = (
        f"CRA review found {len(summarized)} substantive issue(s) in commit {commit}.\n\n"
        "Verify every claim against the current checkout. Fix valid in-scope issues, "
        "rerun the affected validation, and amend the same commit with "
        "`git commit --amend --no-edit`. Do not create a second task commit. The next "
        "Stop attempt will review the amended SHA.\n\n"
        "When every remaining finding is demonstrably invalid or out of scope, record "
        "the rebuttal instead of changing code:\n"
        f"`{shlex.quote(sys.executable)} {shlex.quote(str(script))} rebut "
        f"--commit {shlex.quote(commit)} --reason '<evidence>'`\n\n"
        f"Review findings:\n{body}"
    )
    limit = int(os.environ.get("DAVIS_CRA_MAX_REASON_CHARS", str(DEFAULT_MAX_REASON_CHARS)))
    if len(reason) > limit:
        reason = reason[: max(0, limit - 100)] + "\n...[CRA feedback truncated]"
    return reason


def _failure_reason(commit: str, error: str, attempt: int, maximum: int) -> str:
    return (
        f"CRA reviewer failed for commit {commit} (attempt {attempt}/{maximum}): {error}\n\n"
        "Do not treat this as a clean review. Check authentication, quota, model access, "
        "and the installed Codex CLI, then attempt to stop once more. The gate retries "
        "once and then fails open to avoid trapping the session; report the unresolved "
        "review risk in the final response if the retry also fails."
    )[:DEFAULT_MAX_REASON_CHARS]


def _block(reason: str) -> JsonObject:
    return {"decision": "block", "reason": reason}


def _validate_active_state(state: Mapping[str, Any], repo: Path) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        raise CraError("unsupported CRA state schema")
    if state.get("repo_root") != str(repo):
        raise CraError("CRA state belongs to a different repository")
    if not isinstance(state.get("original_commit"), str):
        raise CraError("CRA state is missing original_commit")
    parents = state.get("boundary_parents")
    if not isinstance(parents, list) or not all(isinstance(item, str) for item in parents):
        raise CraError("CRA state is missing boundary_parents")


def _handle_stop(payload: Mapping[str, Any], codex_home: Path) -> JsonObject:
    if os.environ.get(REVIEWER_GUARD) == "1":
        return {}

    cwd = _payload_cwd(payload)
    try:
        repo = _git_root(cwd)
    except CraError:
        return {}
    root = _state_root(codex_home)
    located = _find_state(root, repo, payload)
    if located is None:
        return {}
    state_path, _ = located

    with _file_lock(_lock_path(state_path)):
        state = _read_json(state_path)
        if state is None:
            return {}
        _validate_active_state(state, repo)
        status = state.get("status")
        if status in {"completed-clean", "completed-rebutted", "failed-open", "cleared"}:
            return {}

        current = _head(repo)
        original = str(state["original_commit"])
        boundary_parents = list(state["boundary_parents"])

        if current != original and status == "armed":
            return _block(
                "CRA was armed for commit "
                f"{original}, but HEAD is now {current} before the first review. "
                "Re-arm the intended coherent task commit or restore the original boundary."
            )
        if not _same_boundary(repo, current, boundary_parents):
            return _block(
                f"CRA must amend one commit boundary. HEAD {current} no longer has the "
                "same parent set as the armed task commit. Restore the task boundary or "
                "clear and deliberately re-arm CRA; do not fold unrelated commits into this loop."
            )
        if not _is_clean(repo):
            return _block(
                "CRA is armed but the worktree is not clean. Validate the current fixes, "
                "stage only the coherent task changes, and amend the same task commit before stopping."
            )

        reviewed_sha = state.get("reviewed_sha")
        if reviewed_sha == current and status == "findings":
            return _block(_findings_reason(state, current))
        if reviewed_sha == current and status == "review-failed":
            failures = int(state.get("failure_count") or 0)
            maximum = int(
                os.environ.get("DAVIS_CRA_MAX_REVIEW_FAILURES", str(DEFAULT_MAX_REVIEW_FAILURES))
            )
            if failures >= maximum:
                state["status"] = "failed-open"
                state["updated_at"] = _utc_now()
                _write_json_atomic(state_path, state)
                return {}

        state["status"] = "reviewing"
        state["current_commit"] = current
        state["updated_at"] = _utc_now()
        _write_json_atomic(state_path, state)

        try:
            review = _run_review(repo, current, root)
        except CraError as exc:
            maximum = int(
                os.environ.get("DAVIS_CRA_MAX_REVIEW_FAILURES", str(DEFAULT_MAX_REVIEW_FAILURES))
            )
            previous_sha = state.get("reviewed_sha")
            previous_failures = int(state.get("failure_count") or 0)
            failures = previous_failures + 1 if previous_sha == current else 1
            state.update(
                {
                    "status": "review-failed" if failures < maximum else "failed-open",
                    "reviewed_sha": current,
                    "failure_count": failures,
                    "last_error": str(exc),
                    "updated_at": _utc_now(),
                }
            )
            _write_json_atomic(state_path, state)
            if failures >= maximum:
                return {}
            return _block(_failure_reason(current, str(exc), failures, maximum))

        findings = review.get("findings")
        correctness = review.get("overall_correctness")
        clean = isinstance(findings, list) and not findings and correctness == "patch is correct"
        state.update(
            {
                "status": "completed-clean" if clean else "findings",
                "reviewed_sha": current,
                "failure_count": 0,
                "last_error": None,
                "last_review": review,
                "updated_at": _utc_now(),
            }
        )
        _write_json_atomic(state_path, state)
        if clean:
            return {}
        return _block(_findings_reason(state, current))


def _arm(args: argparse.Namespace) -> int:
    cwd = Path(args.repo or os.getcwd()).expanduser().absolute()
    repo = _git_root(cwd)
    commit = _ensure_commit(repo, args.commit or "HEAD")
    if commit != _head(repo):
        raise CraError("CRA can only arm the current HEAD commit")
    if not _is_clean(repo):
        raise CraError("refusing to arm CRA with a dirty worktree")
    parents = _commit_parents(repo, commit)
    if len(parents) > 1:
        raise CraError("CRA does not arm merge commits; isolate one coherent task commit")

    codex_home = _codex_home(args.codex_home)
    root = _state_root(codex_home)
    if not args.allow_unconfirmed_hook and not _heartbeat_is_recent(root):
        raise CraError(
            "the CRA hooks have not run in this Codex session. Install and trust them, "
            "then start a new Codex session; otherwise use the documented blocking fallback"
        )

    identity = _identity()
    state_path = _state_path(root, repo, identity)
    thread_id, session_id = _context_ids()
    state: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "repo_root": str(repo),
        "identity": identity,
        "thread_id": thread_id,
        "session_id": session_id,
        "entry_source": args.entry_source,
        "risk": args.risk,
        "original_commit": commit,
        "current_commit": commit,
        "boundary_parents": parents,
        "status": "armed",
        "reviewed_sha": None,
        "failure_count": 0,
        "last_review": None,
        "last_error": None,
        "rebuttal": None,
        "armed_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    with _file_lock(_lock_path(state_path)):
        _write_json_atomic(state_path, state)
        _write_active_pointer(root, repo, state_path, identity)
    print(f"CRA armed for {commit} ({identity})")
    return 0


def _status(args: argparse.Namespace) -> int:
    cwd = Path(args.repo or os.getcwd()).expanduser().absolute()
    repo = _git_root(cwd)
    located = _find_state(_state_root(_codex_home(args.codex_home)), repo)
    if located is None:
        if args.json:
            print("null")
        else:
            print("CRA is not armed for this repository and context")
        return 1
    path, state = located
    if args.json:
        output = dict(state)
        output["state_path"] = str(path)
        print(json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"status={state.get('status')}")
        print(f"original_commit={state.get('original_commit')}")
        print(f"reviewed_sha={state.get('reviewed_sha')}")
        if state.get("last_error"):
            print(f"last_error={state.get('last_error')}")
    return 0


def _rebut(args: argparse.Namespace) -> int:
    cwd = Path(args.repo or os.getcwd()).expanduser().absolute()
    repo = _git_root(cwd)
    root = _state_root(_codex_home(args.codex_home))
    located = _find_state(root, repo)
    if located is None:
        raise CraError("CRA is not armed")
    state_path, _ = located
    with _file_lock(_lock_path(state_path)):
        state = _read_json(state_path)
        if state is None:
            raise CraError("CRA state disappeared")
        _validate_active_state(state, repo)
        current = _ensure_commit(repo, args.commit or "HEAD")
        if current != _head(repo):
            raise CraError("rebuttal must target the current HEAD")
        if state.get("status") != "findings" or state.get("reviewed_sha") != current:
            raise CraError("rebuttal is allowed only for the current reviewed SHA with findings")
        if not _is_clean(repo):
            raise CraError("rebuttal requires a clean worktree")
        reason = args.reason.strip()
        if len(reason) < 12:
            raise CraError("rebuttal must include concrete evidence, not a bare dismissal")
        state.update(
            {
                "status": "completed-rebutted",
                "rebuttal": {
                    "commit": current,
                    "reason": reason,
                    "recorded_at": _utc_now(),
                },
                "updated_at": _utc_now(),
            }
        )
        _write_json_atomic(state_path, state)
    print(f"CRA findings rebutted for {current}")
    return 0


def _clear(args: argparse.Namespace) -> int:
    cwd = Path(args.repo or os.getcwd()).expanduser().absolute()
    repo = _git_root(cwd)
    root = _state_root(_codex_home(args.codex_home))
    located = _find_state(root, repo)
    if located is None:
        print("CRA is not armed")
        return 0
    state_path, _ = located
    with _file_lock(_lock_path(state_path)):
        state = _read_json(state_path) or {}
        state.update(
            {
                "status": "cleared",
                "clear_reason": args.reason,
                "updated_at": _utc_now(),
            }
        )
        _write_json_atomic(state_path, state)
    print(f"CRA state cleared: {state_path}")
    return 0


def _is_managed_handler(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    return any(
        isinstance(value, str) and MANAGED_HOOK_MARKER in value
        for value in (handler.get("command"), handler.get("commandWindows"))
    )


def _managed_handler(script: Path, action: str) -> JsonObject:
    python = Path(sys.executable).expanduser().absolute()
    command = (
        f"{MANAGED_HOOK_MARKER} "
        f"{shlex.quote(str(python))} {shlex.quote(str(script))} {shlex.quote(action)}"
    )
    windows = f"set {MANAGED_HOOK_MARKER}&& \"{python}\" \"{script}\" {action}"
    handler: JsonObject = {
        "type": "command",
        "command": command,
        "commandWindows": windows,
        "timeout": DEFAULT_HOOK_TIMEOUT_SECONDS if action == "hook" else 30,
    }
    if action == "hook":
        handler["statusMessage"] = "Running CRA commit review"
        handler["additionalContextLimit"] = DEFAULT_MAX_REASON_CHARS
    return handler


def _remove_managed_groups(groups: object) -> list[Any]:
    if groups is None:
        return []
    if not isinstance(groups, list):
        raise CraError("hook event configuration must be an array")
    output: list[Any] = []
    for group in groups:
        if not isinstance(group, dict):
            output.append(group)
            continue
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            output.append(group)
            continue
        kept = [handler for handler in handlers if not _is_managed_handler(handler)]
        if kept:
            replacement = dict(group)
            replacement["hooks"] = kept
            output.append(replacement)
    return output


def _load_hooks_document(path: Path) -> JsonObject:
    if not path.exists():
        return {"hooks": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CraError(f"refusing to modify invalid hooks file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CraError("hooks.json root must be an object")
    hooks = value.get("hooks")
    if hooks is None:
        value["hooks"] = {}
    elif not isinstance(hooks, dict):
        raise CraError("hooks.json 'hooks' value must be an object")
    return value


def _install_hook(args: argparse.Namespace) -> int:
    codex_home = _codex_home(args.codex_home)
    path = codex_home / "hooks.json"
    document = _load_hooks_document(path)
    hooks = document["hooks"]
    assert isinstance(hooks, dict)
    installed_script = codex_home / "davis-agent-kit" / "scripts" / "cra_gate.py"
    script = installed_script.absolute() if installed_script.exists() else Path(__file__).absolute()
    for event, action in (("SessionStart", "heartbeat"), ("Stop", "hook")):
        groups = _remove_managed_groups(hooks.get(event))
        groups.append({"hooks": [_managed_handler(script, action)]})
        hooks[event] = groups

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.with_name(f"{path.name}.bak").write_bytes(path.read_bytes())
    _write_json_atomic(path, document)
    print(f"Installed CRA SessionStart and Stop hooks in {path}")
    print("Trust the updated hooks in Codex and start a new session before arming CRA.")
    return 0


def _uninstall_hook(args: argparse.Namespace) -> int:
    path = _codex_home(args.codex_home) / "hooks.json"
    document = _load_hooks_document(path)
    hooks = document["hooks"]
    assert isinstance(hooks, dict)
    for event in ("SessionStart", "Stop"):
        groups = _remove_managed_groups(hooks.get(event))
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    _write_json_atomic(path, document)
    print(f"Removed managed CRA hooks from {path}")
    return 0


def _doctor_hook(args: argparse.Namespace) -> int:
    codex_home = _codex_home(args.codex_home)
    path = codex_home / "hooks.json"
    document = _load_hooks_document(path)
    hooks = document.get("hooks")
    assert isinstance(hooks, dict)
    problems: list[str] = []
    for event in ("SessionStart", "Stop"):
        groups = hooks.get(event)
        count = 0
        if isinstance(groups, list):
            for group in groups:
                if isinstance(group, dict) and isinstance(group.get("hooks"), list):
                    count += sum(_is_managed_handler(item) for item in group["hooks"])
        if count != 1:
            problems.append(f"{event}: expected 1 managed handler, found {count}")
    active = _heartbeat_is_recent(_state_root(codex_home))
    if args.json:
        print(
            json.dumps(
                {
                    "hooks_file": str(path),
                    "configured": not problems,
                    "session_heartbeat": active,
                    "problems": problems,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        if problems:
            for problem in problems:
                print(f"FAIL {problem}")
        else:
            print(f"OK managed CRA hooks are installed in {path}")
        if active:
            print("OK a trusted hook heartbeat has run recently")
        else:
            print("WARN no recent hook heartbeat; trust hooks and start a new Codex session")
    return 1 if problems else 0


def _hook_command(args: argparse.Namespace) -> int:
    payload = _read_hook_payload()
    try:
        result = _handle_stop(payload, _codex_home(args.codex_home))
    except Exception as exc:  # A broken hook must not trap the user indefinitely.
        print(f"CRA Stop hook failed open: {exc}", file=sys.stderr)
        result = {}
    _emit_hook(result)
    return 0


def _heartbeat_command(args: argparse.Namespace) -> int:
    payload = _read_hook_payload()
    try:
        _record_heartbeat(payload, _codex_home(args.codex_home))
    except Exception as exc:
        print(f"CRA heartbeat hook failed open: {exc}", file=sys.stderr)
    _emit_hook({})
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", help="override CODEX_HOME")
    subparsers = parser.add_subparsers(dest="command", required=True)

    arm = subparsers.add_parser("arm", help="arm one exact CRA commit boundary")
    arm.add_argument("--repo", help="repository path; defaults to cwd")
    arm.add_argument("--commit", help="commit to arm; defaults to HEAD")
    arm.add_argument(
        "--entry-source",
        required=True,
        choices=("explicit-request", "tca-required", "autonomous-risk"),
    )
    arm.add_argument("--risk", help="required rationale for autonomous-risk")
    arm.add_argument(
        "--allow-unconfirmed-hook",
        action="store_true",
        help="testing/manual escape hatch; normally require a trusted SessionStart heartbeat",
    )
    arm.set_defaults(func=_arm)

    status = subparsers.add_parser("status", help="show CRA state")
    status.add_argument("--repo")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=_status)

    rebut = subparsers.add_parser("rebut", help="record an evidence-backed rebuttal")
    rebut.add_argument("--repo")
    rebut.add_argument("--commit")
    rebut.add_argument("--reason", required=True)
    rebut.set_defaults(func=_rebut)

    clear = subparsers.add_parser("clear", help="clear a stale or deliberately abandoned gate")
    clear.add_argument("--repo")
    clear.add_argument("--reason", required=True)
    clear.set_defaults(func=_clear)

    hook = subparsers.add_parser("hook", help=argparse.SUPPRESS)
    hook.set_defaults(func=_hook_command)

    heartbeat = subparsers.add_parser("heartbeat", help=argparse.SUPPRESS)
    heartbeat.set_defaults(func=_heartbeat_command)

    install = subparsers.add_parser("install-hook", help="merge managed hooks into hooks.json")
    install.set_defaults(func=_install_hook)

    uninstall = subparsers.add_parser("uninstall-hook", help="remove only managed CRA hooks")
    uninstall.set_defaults(func=_uninstall_hook)

    doctor = subparsers.add_parser("doctor-hook", help="check managed hook configuration")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_doctor_hook)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "arm" and args.entry_source == "autonomous-risk" and not args.risk:
        parser.error("--risk is required for autonomous-risk")
    try:
        return int(args.func(args))
    except CraError as exc:
        print(f"CRA error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
