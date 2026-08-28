#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ALLOWED_PATHS = ("src/labels.py", "tests/test_labels.py")


def run(
    args: list[str],
    *,
    cwd: Path,
    input_bytes: bytes | None = None,
) -> bytes:
    completed = subprocess.run(
        args,
        cwd=cwd,
        input=input_bytes,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout


def git_text(repo: Path, *args: str) -> str:
    return run(["git", *args], cwd=repo).decode("utf-8").strip()


def git_paths(repo: Path, *args: str) -> set[str]:
    raw = run(["git", *args, "-z"], cwd=repo)
    return {
        item.decode("utf-8")
        for item in raw.split(b"\0")
        if item
    }


def clean_change_set(repo: Path) -> set[str]:
    staged = git_paths(repo, "diff", "--cached", "--name-only")
    unstaged = git_paths(repo, "diff", "--name-only")
    untracked = git_paths(repo, "ls-files", "--others", "--exclude-standard")
    return staged | unstaged | untracked


def ensure_worktree(path: Path, label: str) -> Path:
    root = Path(git_text(path, "rev-parse", "--show-toplevel")).resolve()
    if root != path.resolve():
        raise SystemExit(f"{label} must be a worktree root: {path} -> {root}")
    return root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Integrate an allowed uncommitted task diff from an isolated worktree "
            "into the reconciled primary fixture worktree without committing."
        )
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--expected-base", required=True)
    parser.add_argument("--writer-stopped-marker", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = ensure_worktree(args.source.expanduser().resolve(), "source")
    target = ensure_worktree(args.target.expanduser().resolve(), "target")
    if source.samefile(target):
        raise SystemExit("source and target worktrees must be different")

    marker = args.writer_stopped_marker.expanduser().resolve()
    if not marker.is_file():
        raise SystemExit(f"writer terminal marker is missing: {marker}")
    marker_data = json.loads(marker.read_text(encoding="utf-8"))
    recorded_repo = Path(marker_data.get("repo", "")).resolve()
    if recorded_repo != target:
        raise SystemExit(
            f"writer marker belongs to {recorded_repo}, expected target {target}"
        )

    expected_base = git_text(target, "rev-parse", f"{args.expected_base}^{{commit}}")
    source_head = git_text(source, "rev-parse", "HEAD")
    target_head = git_text(target, "rev-parse", "HEAD")
    if source_head != expected_base:
        raise SystemExit(
            f"source HEAD changed or was committed: {source_head} != {expected_base}"
        )
    if target_head != expected_base:
        raise SystemExit(
            f"target HEAD changed before integration: {target_head} != {expected_base}"
        )

    allowed = set(ALLOWED_PATHS)
    source_changes = clean_change_set(source)
    if source_changes != allowed:
        raise SystemExit(
            "isolated worktree must contain exactly the task files; "
            f"observed {sorted(source_changes)}"
        )
    target_changes_before = clean_change_set(target)
    if target_changes_before:
        raise SystemExit(
            "target worktree is not reconciled and clean before integration: "
            f"{sorted(target_changes_before)}"
        )

    staged_source = git_paths(source, "diff", "--cached", "--name-only")
    if staged_source:
        raise SystemExit(
            f"isolated result must remain unstaged and uncommitted: {sorted(staged_source)}"
        )

    run(["git", "diff", "--check"], cwd=source)
    patch = run(
        [
            "git",
            "diff",
            "--binary",
            "--no-ext-diff",
            expected_base,
            "--",
            *ALLOWED_PATHS,
        ],
        cwd=source,
    )
    if not patch:
        raise SystemExit("isolated worktree produced an empty task patch")

    run(["git", "apply", "--check", "-"], cwd=target, input_bytes=patch)
    run(["git", "apply", "-"], cwd=target, input_bytes=patch)
    run(["git", "diff", "--check"], cwd=target)

    target_changes_after = clean_change_set(target)
    if target_changes_after != allowed:
        raise SystemExit(
            "integrated target must contain exactly the task files; "
            f"observed {sorted(target_changes_after)}"
        )
    if git_text(target, "rev-parse", "HEAD") != expected_base:
        raise SystemExit("integration unexpectedly created or moved a target commit")
    if clean_change_set(source) != allowed:
        raise SystemExit("source worktree changed during integration")

    manifest_path = args.manifest.expanduser().resolve(strict=False)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists() or manifest_path.is_symlink():
        raise SystemExit(f"refusing to overwrite integration manifest: {manifest_path}")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "source_worktree": str(source),
        "target_worktree": str(target),
        "expected_base": expected_base,
        "source_head": source_head,
        "target_head_before": target_head,
        "target_head_after": git_text(target, "rev-parse", "HEAD"),
        "writer_stopped_marker": str(marker),
        "writer_marker": marker_data,
        "allowed_paths": list(ALLOWED_PATHS),
        "source_changes": sorted(source_changes),
        "target_changes_before": sorted(target_changes_before),
        "target_changes_after": sorted(target_changes_after),
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
        "patch_size_bytes": len(patch),
        "commit_created": False,
        "target_oracle_required_after_integration": True,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
