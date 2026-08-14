#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - this kit's installer is POSIX-oriented.
    fcntl = None  # type: ignore[assignment]


SCHEMA_VERSION = 1
HOOK_VERSION = 1
REVIEW_MODEL = "gpt-5.6-sol"
REVIEW_EFFORT = "max"
REVIEW_TIMEOUT_SECONDS = 6_900
HOOK_TIMEOUT_SECONDS = 7_200
REVIEW_CHILD_ENV = "DAVIS_CRA_REVIEW_CHILD"
ENTRY_SOURCES = ("explicit-request", "tca-required", "autonomous-risk")


class CraError(RuntimeError):
    pass


class CraFallback(CraError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def codex_home(env: dict[str, str]) -> Path:
    return Path(env.get("CODEX_HOME") or "~/.codex").expanduser().resolve(strict=False)


def session_id(env: dict[str, str]) -> str:
    for name in ("CODEX_SESSION_ID", "CODEX_THREAD_ID"):
        value = env.get(name, "").strip()
        if value:
            if "\x00" in value or len(value) > 512:
                raise CraFallback(f"{name} is not a usable session identifier")
            return value
    raise CraFallback(
        "Codex did not expose CODEX_SESSION_ID or CODEX_THREAD_ID; "
        "use the blocking CRA command"
    )


def ensure_private_dir(path: Path, label: str) -> None:
    if path.is_symlink():
        raise CraError(f"{label} must not be a symlink: {path}")
    path.mkdir(exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise CraError(f"{label} is not a directory: {path}")
    try:
        path.chmod(0o700)
    except OSError:
        pass


def paths(home: Path, sid: str) -> tuple[Path, Path, Path]:
    home.mkdir(parents=True, exist_ok=True)
    root = home / "davis-cra"
    ensure_private_dir(root, "CRA runtime root")
    sessions = root / "sessions"
    ensure_private_dir(sessions, "CRA sessions root")
    directory = sessions / hashlib.sha256(sid.encode()).hexdigest()
    ensure_private_dir(directory, "CRA session directory")
    return directory, directory / "state.json", directory / "lock"


@contextmanager
def lock_file(path: Path, *, blocking: bool) -> Iterator[bool]:
    if fcntl is None:
        raise CraFallback("hook-managed CRA requires POSIX file locking")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    acquired = False
    try:
        operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(fd, operation)
        except BlockingIOError:
            yield False
            return
        acquired = True
        yield True
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def empty_state(sid: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": sid,
        "sequence": 0,
        "active": None,
        "pending": None,
        "last_result": None,
    }


def read_state(path: Path, sid: str) -> dict[str, Any]:
    if not path.exists():
        return empty_state(sid)
    if path.is_symlink():
        raise CraError(f"CRA state must not be a symlink: {path}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CraError(f"cannot read CRA state: {exc}") from exc
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION:
        raise CraError("CRA state schema is invalid")
    if state.get("session_id") != sid:
        raise CraError("CRA state belongs to another session")
    return state


def write_state(path: Path, state: dict[str, Any]) -> None:
    fd, name = tempfile.mkstemp(prefix=".state.", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def git(repo: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(repo), *args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode(errors="replace").strip()
        raise CraError(f"git {' '.join(args)} failed: {detail or completed.returncode}")
    return completed.stdout


def git_text(repo: Path, *args: str) -> str:
    return git(repo, *args).decode().strip()


def repo_root(candidate: Path) -> Path:
    candidate = candidate.expanduser().resolve(strict=True)
    return Path(git_text(candidate, "rev-parse", "--show-toplevel")).resolve(strict=True)


def status_digest(repo: Path) -> str:
    status = git(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    return hashlib.sha256(status).hexdigest()


def reviewer_binary() -> Path:
    executable = shutil.which("codex")
    if executable is None:
        raise CraFallback("codex executable is unavailable; use the blocking CRA command")
    return Path(executable).resolve(strict=True)


def activate(payload: dict[str, Any], env: dict[str, str]) -> None:
    sid = str(payload.get("session_id") or "").strip()
    if not sid:
        raise CraError("hook input is missing session_id")
    _, state_path, lock_path = paths(codex_home(env), sid)
    with lock_file(lock_path, blocking=True):
        state = read_state(state_path, sid)
        state["active"] = {
            "hook_version": HOOK_VERSION,
            "event": payload.get("hook_event_name"),
            "cwd": str(payload.get("cwd") or ""),
            "at": now(),
        }
        write_state(state_path, state)


def prepare(args: argparse.Namespace, env: dict[str, str]) -> int:
    if env.get(REVIEW_CHILD_ENV) == "1":
        raise CraFallback("reviewer child sessions may not schedule CRA")
    sid = session_id(env)
    _, state_path, lock_path = paths(codex_home(env), sid)
    repo = repo_root(args.repo)
    commit = git_text(repo, "rev-parse", "--verify", f"{args.commit}^{{commit}}")
    head = git_text(repo, "rev-parse", "HEAD")
    if commit != head:
        raise CraFallback(f"CRA commit {commit} is not current HEAD {head}")
    rationale = (args.risk_rationale or "").strip()
    if args.entry_source == "autonomous-risk" and not rationale:
        raise CraError("autonomous-risk requires --risk-rationale")

    boundary = {
        "repo_root": str(repo),
        "commit_sha": commit,
        "status_sha256": status_digest(repo),
        "entry_source": args.entry_source,
        "risk_rationale": rationale,
        "reviewer_binary": str(reviewer_binary()),
        "review_model": REVIEW_MODEL,
        "review_effort": REVIEW_EFFORT,
    }
    with lock_file(lock_path, blocking=True):
        state = read_state(state_path, sid)
        active = state.get("active")
        if not isinstance(active, dict) or active.get("hook_version") != HOOK_VERSION:
            raise CraFallback(
                "the Davis CRA hook has not run in this session; review it with /hooks, "
                "start a new session or submit another prompt, or use blocking CRA"
            )
        pending = state.get("pending")
        if isinstance(pending, dict):
            if pending.get("phase") == "pending" and all(
                pending.get(key) == value for key, value in boundary.items()
            ):
                print(
                    json.dumps(
                        {
                            "status": "prepared",
                            "mode": "stop-hook",
                            "idempotent": True,
                            "attempt": pending["attempt"],
                            "commit": commit,
                        }
                    )
                )
                return 0
            raise CraError("another CRA attempt is already pending or running")
        attempt = int(state.get("sequence") or 0) + 1
        state["sequence"] = attempt
        state["pending"] = {
            **boundary,
            "attempt": attempt,
            "phase": "pending",
            "prepared_at": now(),
        }
        write_state(state_path, state)
    print(
        json.dumps(
            {
                "status": "prepared",
                "mode": "stop-hook",
                "idempotent": False,
                "attempt": attempt,
                "commit": commit,
                "next": "end the current turn; do not run or poll codex review",
            }
        )
    )
    return 0


def related(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def failure(
    state: dict[str, Any], state_path: Path, pending: dict[str, Any], message: str
) -> dict[str, str]:
    result = {
        "state": "failed",
        "attempt": pending.get("attempt"),
        "repo_root": pending.get("repo_root"),
        "commit_sha": pending.get("commit_sha"),
        "error": message,
        "completed_at": now(),
    }
    state["last_result"] = result
    state["pending"] = None
    write_state(state_path, state)
    return {
        "decision": "block",
        "reason": (
            "CRA CONTINUATION\nstate=failed\n"
            f"attempt={result['attempt']}\nrepo={result['repo_root']}\n"
            f"commit={result['commit_sha']}\nerror={message}\n\n"
            "Do not claim CRA is clean. Diagnose the failure against the current checkout. "
            "Retry only after correcting the cause and preparing a new attempt; otherwise "
            "report the failed state and remaining risk."
        ),
    }


def open_log(path: Path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    return os.fdopen(os.open(path, flags, 0o600), "wb", buffering=0)


def tail(path: Path, limit: int = 8_000) -> str:
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        start = max(0, stream.tell() - limit)
        stream.seek(start)
        text = stream.read().decode(errors="replace")
    return ("[earlier output omitted; read the full log]\n" if start else "") + text


def review_command(reviewer: Path, commit: str) -> list[str]:
    return [
        str(reviewer),
        "review",
        "--commit",
        commit,
        "-c",
        f'model="{REVIEW_MODEL}"',
        "-c",
        f'model_reasoning_effort="{REVIEW_EFFORT}"',
    ]


def handle_stop(payload: dict[str, Any], env: dict[str, str]) -> dict[str, str] | None:
    sid = str(payload.get("session_id") or "").strip()
    cwd = str(payload.get("cwd") or "").strip()
    if not sid or not cwd:
        raise CraError("Stop hook input must include session_id and cwd")
    directory, state_path, lock_path = paths(codex_home(env), sid)
    if not state_path.exists():
        return None

    with lock_file(lock_path, blocking=False) as acquired:
        if not acquired:
            return None
        state = read_state(state_path, sid)
        pending = state.get("pending")
        if not isinstance(pending, dict):
            return None
        if pending.get("phase") == "running":
            return failure(
                state,
                state_path,
                pending,
                "a previous attempt entered running state without a terminal result; "
                "automatic re-execution is disabled to prevent duplicate usage",
            )
        if pending.get("phase") != "pending":
            return failure(state, state_path, pending, "invalid pending CRA phase")

        try:
            repo = Path(pending["repo_root"]).resolve(strict=True)
            hook_cwd = Path(cwd).expanduser().resolve(strict=True)
            if not related(repo, hook_cwd):
                raise CraError("hook cwd is unrelated to the prepared repository")
            commit = git_text(repo, "rev-parse", "--verify", f"{pending['commit_sha']}^{{commit}}")
            if git_text(repo, "rev-parse", "HEAD") != commit:
                raise CraError("HEAD moved after CRA was prepared")
            if status_digest(repo) != pending.get("status_sha256"):
                raise CraError("worktree or index changed after CRA was prepared")
            if pending.get("review_model") != REVIEW_MODEL or pending.get("review_effort") != REVIEW_EFFORT:
                raise CraError("prepared reviewer settings do not match the fixed CRA settings")
            reviewer = Path(pending["reviewer_binary"]).resolve(strict=True)
            if reviewer != reviewer_binary():
                raise CraError("the codex executable changed after CRA was prepared")
        except (CraError, CraFallback, OSError, KeyError, ValueError) as exc:
            return failure(state, state_path, pending, str(exc))

        attempt = int(pending["attempt"])
        log_path = directory / f"review-{attempt:04d}.log"
        pending.update(
            phase="running",
            started_at=now(),
            turn_id=payload.get("turn_id"),
            log_path=str(log_path),
        )
        write_state(state_path, state)

        command = review_command(reviewer, commit)
        exit_code: int | None = None
        timed_out = False
        try:
            with open_log(log_path) as log:
                log.write(
                    (
                        f"CRA attempt={attempt}\ncommit={commit}\nmodel={REVIEW_MODEL}\n"
                        f"reasoning_effort={REVIEW_EFFORT}\n\n"
                    ).encode()
                )
                child_env = dict(env)
                child_env[REVIEW_CHILD_ENV] = "1"
                child_env.pop("CODEX_SESSION_ID", None)
                child_env.pop("CODEX_THREAD_ID", None)
                process = subprocess.Popen(
                    command,
                    cwd=repo,
                    env=child_env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:
                    exit_code = process.wait(timeout=REVIEW_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                        process.wait(timeout=10)
                    except (ProcessLookupError, subprocess.TimeoutExpired):
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                    exit_code = 124
        except (OSError, subprocess.SubprocessError) as exc:
            return failure(state, state_path, pending, str(exc))

        result_state = "completed-output" if exit_code == 0 and not timed_out else "failed"
        state["last_result"] = {
            "state": result_state,
            "attempt": attempt,
            "repo_root": str(repo),
            "commit_sha": commit,
            "review_exit": exit_code,
            "timed_out": timed_out,
            "log_path": str(log_path),
            "completed_at": now(),
        }
        state["pending"] = None
        write_state(state_path, state)
        action = (
            "Read the full log. Exit 0 proves only that reviewer transport completed, not that "
            "the review is clean. Verify every finding. Fix valid findings, rerun local validation, "
            "amend the same commit, prepare CRA again, and end the turn. Finish only when the "
            "review is clean or remaining findings are explicitly rebuttable."
            if result_state == "completed-output"
            else "Treat CRA as failed. Inspect the full log, correct the failure, and do not claim "
            "the review is clean."
        )
        return {
            "decision": "block",
            "reason": (
                "CRA CONTINUATION\n"
                f"state={result_state}\nattempt={attempt}\nrepo={repo}\ncommit={commit}\n"
                f"review_exit={exit_code}\ntimed_out={str(timed_out).lower()}\n"
                f"log_path={log_path}\n\n{action}\n\n"
                f"--- terminal review output ---\n{tail(log_path)}"
            ),
        }


def hook_config(env: dict[str, str]) -> int:
    controller = codex_home(env) / "davis-agent-kit" / "scripts" / "cra_control.py"
    if not controller.is_file():
        raise CraError(
            f"managed CRA controller is missing: {controller}; "
            "run scripts/install_codex.sh first"
        )
    command = f"python3 {shlex.quote(str(controller))} hook"
    short_hook = {"type": "command", "command": command, "timeout": 5}
    stop_hook = {
        "type": "command",
        "command": command,
        "timeout": HOOK_TIMEOUT_SECONDS,
        "statusMessage": "Running CRA review; this session will continue when it finishes",
    }
    print(
        json.dumps(
            {
                "description": (
                    "Continue Davis CRA in the same Codex session after the review finishes."
                ),
                "hooks": {
                    "SessionStart": [{"hooks": [short_hook]}],
                    "UserPromptSubmit": [{"hooks": [short_hook]}],
                    "Stop": [{"hooks": [stop_hook]}],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def consume_hook(env: dict[str, str]) -> int:
    if env.get(REVIEW_CHILD_ENV) == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise CraError(f"invalid hook JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CraError("hook input must be a JSON object")
    event = payload.get("hook_event_name")
    if event in {"SessionStart", "UserPromptSubmit"}:
        activate(payload, env)
    elif event == "Stop":
        response = handle_stop(payload, env)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Prepare and deliver hook-managed Davis CRA reviews."
    )
    commands = result.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--repo", type=Path, default=Path.cwd())
    prepare_parser.add_argument("--commit", required=True)
    prepare_parser.add_argument("--entry-source", choices=ENTRY_SOURCES, required=True)
    prepare_parser.add_argument("--risk-rationale")
    commands.add_parser("hook")
    commands.add_parser("hook-config")
    return result


def main(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    args = parser().parse_args(argv)
    env = dict(os.environ if environ is None else environ)
    try:
        if args.command == "prepare":
            return prepare(args, env)
        if args.command == "hook":
            return consume_hook(env)
        if args.command == "hook-config":
            return hook_config(env)
        raise CraError(f"unsupported command: {args.command}")
    except CraFallback as exc:
        print(json.dumps({"status": "fallback-required", "reason": str(exc)}))
        return 3
    except CraError as exc:
        print(f"CRA control failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
