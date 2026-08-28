#!/usr/bin/env python3
"""Observe and compare a Git worktree binding without mutating it."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def _git(
    repo: Path, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} exited {completed.returncode}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed


def _decode(value: bytes) -> str:
    return value.decode("utf-8", "surrogateescape")


def _nul_values(value: bytes) -> list[str]:
    return [_decode(item) for item in value.split(b"\0") if item]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _status_paths(records: list[str]) -> list[str]:
    paths: list[str] = []
    for record in records:
        path = record[3:] if len(record) >= 3 and record[2] == " " else record
        if path and path not in paths:
            paths.append(path)
    return sorted(paths)


def _snapshot(repo: Path) -> dict[str, Any]:
    requested = repo.expanduser().resolve(strict=True)
    worktree = Path(
        _decode(_git(requested, ["rev-parse", "--show-toplevel"]).stdout).strip()
    ).resolve(strict=True)
    git_dir = Path(
        _decode(_git(worktree, ["rev-parse", "--absolute-git-dir"]).stdout).strip()
    ).resolve(strict=True)
    common_dir = Path(
        _decode(_git(worktree, ["rev-parse", "--git-common-dir"]).stdout).strip()
    )
    if not common_dir.is_absolute():
        common_dir = (worktree / common_dir).resolve(strict=True)
    else:
        common_dir = common_dir.resolve(strict=True)

    head = _decode(_git(worktree, ["rev-parse", "HEAD"]).stdout).strip()
    branch_result = _git(
        worktree, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False
    )
    detached = branch_result.returncode != 0
    branch = "DETACHED" if detached else _decode(branch_result.stdout).strip()

    status_raw = _git(
        worktree,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
    ).stdout
    status_records = _nul_values(status_raw)
    status_paths = _status_paths(status_records)
    staged = _nul_values(
        _git(worktree, ["diff", "--cached", "--name-only", "-z"]).stdout
    )
    unstaged = _nul_values(
        _git(worktree, ["diff", "--name-only", "-z"]).stdout
    )
    untracked = _nul_values(
        _git(
            worktree,
            ["ls-files", "--others", "--exclude-standard", "-z"],
        ).stdout
    )
    refs_raw = _git(
        worktree,
        ["for-each-ref", "--format=%(refname)%00%(objectname)%00"],
    ).stdout
    reflog_result = _git(
        worktree,
        ["reflog", "show", "--all", "--format=%H%x00%gD%x00%gs"],
        check=False,
    )
    worktrees_raw = _git(worktree, ["worktree", "list", "--porcelain", "-z"]).stdout

    identity = {
        "canonical_worktree": str(worktree),
        "git_dir": str(git_dir),
        "git_common_dir": str(common_dir),
        "branch": branch,
        "detached": detached,
        "head": head,
        "status_sha256": _sha256(status_raw),
        "status_records": status_records,
        "status_paths": status_paths,
        "staged_paths": sorted(staged),
        "unstaged_paths": sorted(unstaged),
        "untracked_paths": sorted(untracked),
        "clean": not status_records,
        "refs_sha256": _sha256(refs_raw),
        "reflog_sha256": _sha256(reflog_result.stdout),
        "reflog_available": reflog_result.returncode == 0,
        "worktree_list_sha256": _sha256(worktrees_raw),
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "git-worktree-binding",
        "requested_path": str(requested),
        "observed_at_unix_ns": time.time_ns(),
        "monotonic_ns": time.monotonic_ns(),
        **identity,
        "binding_fingerprint": fingerprint,
    }


def observe_binding(repo: Path, *, stability_delay_ms: int = 0) -> dict[str, Any]:
    first = _snapshot(repo)
    if stability_delay_ms <= 0:
        first["stability"] = {
            "sample_count": 1,
            "delay_ms": 0,
            "stable": True,
            "first_fingerprint": first["binding_fingerprint"],
            "second_fingerprint": first["binding_fingerprint"],
        }
        return first
    time.sleep(stability_delay_ms / 1000)
    second = _snapshot(repo)
    second["stability"] = {
        "sample_count": 2,
        "delay_ms": stability_delay_ms,
        "stable": first["binding_fingerprint"] == second["binding_fingerprint"],
        "first_fingerprint": first["binding_fingerprint"],
        "second_fingerprint": second["binding_fingerprint"],
    }
    return second


def compare_binding(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    allowed_edit_paths: set[str],
    commit_forbidden: bool = True,
) -> dict[str, Any]:
    changed_paths = set(after.get("status_paths", []))
    checks = {
        "same_worktree": before.get("canonical_worktree")
        == after.get("canonical_worktree"),
        "same_git_dir": before.get("git_dir") == after.get("git_dir"),
        "stable_after": after.get("stability", {}).get("stable") is True,
        "changed_paths_permitted": changed_paths <= allowed_edit_paths,
        "staged_empty": not after.get("staged_paths"),
        "head_unchanged": before.get("head") == after.get("head"),
        "branch_unchanged": before.get("branch") == after.get("branch"),
        "refs_unchanged": before.get("refs_sha256") == after.get("refs_sha256"),
        "reflog_unchanged": before.get("reflog_sha256")
        == after.get("reflog_sha256"),
        "worktree_list_unchanged": before.get("worktree_list_sha256")
        == after.get("worktree_list_sha256"),
    }
    required = [
        "same_worktree",
        "same_git_dir",
        "stable_after",
        "changed_paths_permitted",
        "staged_empty",
        "worktree_list_unchanged",
    ]
    if commit_forbidden:
        required.extend(
            ["head_unchanged", "branch_unchanged", "refs_unchanged", "reflog_unchanged"]
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "git-worktree-mutation-audit",
        "allowed_edit_paths": sorted(allowed_edit_paths),
        "commit_forbidden": commit_forbidden,
        "changed_paths": sorted(changed_paths),
        "checks": checks,
        "failed_checks": [name for name in required if not checks[name]],
        "passed": all(checks[name] for name in required),
        "before_fingerprint": before.get("binding_fingerprint"),
        "after_fingerprint": after.get("binding_fingerprint"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--stability-delay-ms", type=int, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare-before", type=Path)
    parser.add_argument("--allowed-edit-path", action="append", default=[])
    parser.add_argument("--commit-forbidden", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    observation = observe_binding(
        args.repo, stability_delay_ms=max(0, args.stability_delay_ms)
    )
    document: dict[str, Any] = {"observation": observation}
    if args.compare_before:
        before_doc = json.loads(args.compare_before.read_text(encoding="utf-8"))
        before = before_doc.get("observation", before_doc)
        document["audit"] = compare_binding(
            before,
            observation,
            allowed_edit_paths=set(args.allowed_edit_path),
            commit_forbidden=args.commit_forbidden,
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("BINDING_OBSERVATION:" + json.dumps(observation, ensure_ascii=False, sort_keys=True))
    if "audit" in document:
        print("BINDING_AUDIT:" + json.dumps(document["audit"], ensure_ascii=False, sort_keys=True))
        if not document["audit"]["passed"]:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
