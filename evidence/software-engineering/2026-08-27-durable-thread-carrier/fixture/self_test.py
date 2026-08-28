#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(args), flush=True)
    completed = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout, end="")
    print(f"exit={completed.returncode}", flush=True)
    if expect_success and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    if not expect_success and completed.returncode == 0:
        raise SystemExit("command unexpectedly succeeded")
    return completed


def wait_for(path: Path, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise SystemExit(f"timed out waiting for {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--candidate-commit", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_dir = Path(__file__).resolve().parent
    root = args.root.expanduser().resolve(strict=False)
    source_repo = args.source_repo.expanduser().resolve()

    run([sys.executable, str(fixture_dir / "setup.py"), "--root", str(root)])
    metadata = json.loads((root / "fixture-metadata.json").read_text(encoding="utf-8"))
    repo = Path(metadata["repo"])
    state = Path(metadata["state"])
    primary_sha = metadata["primary_sha"]

    baseline_policy_dir = root / "policy-baseline"
    candidate_policy_dir = root / "policy-candidate"
    run(
        [
            sys.executable,
            str(fixture_dir / "install_policy.py"),
            "--source-repo",
            str(source_repo),
            "--policy-commit",
            args.baseline_commit,
            "--policy-side",
            "baseline",
            "--run-dir",
            str(baseline_policy_dir),
        ]
    )
    run(
        [
            sys.executable,
            str(fixture_dir / "install_policy.py"),
            "--source-repo",
            str(source_repo),
            "--policy-commit",
            args.candidate_commit,
            "--policy-side",
            "candidate",
            "--run-dir",
            str(candidate_policy_dir),
        ]
    )

    baseline_manifest = json.loads(
        (baseline_policy_dir / "policy-load-manifest.json").read_text(encoding="utf-8")
    )
    candidate_manifest = json.loads(
        (candidate_policy_dir / "policy-load-manifest.json").read_text(encoding="utf-8")
    )
    if baseline_manifest["resolved_commit"] != args.baseline_commit:
        raise SystemExit("baseline policy commit was not loaded exactly")
    if candidate_manifest["resolved_commit"] != args.candidate_commit:
        raise SystemExit("candidate policy commit was not loaded exactly")
    baseline_skill = baseline_manifest["identities"]["software_engineering_tree"]
    candidate_skill = candidate_manifest["identities"]["software_engineering_tree"]
    if baseline_skill["sha256"] == candidate_skill["sha256"]:
        raise SystemExit("baseline and candidate unexpectedly load the same skill tree")
    if baseline_manifest["codex_home"] == candidate_manifest["codex_home"]:
        raise SystemExit("baseline and candidate reused a Codex home")
    print("policy installation identity self-test passed")

    run(
        [
            sys.executable,
            str(fixture_dir / "verify.py"),
            "--repo",
            str(repo),
        ],
        expect_success=False,
    )

    isolated = root / "isolated-writer"
    run(
        [
            "git",
            "worktree",
            "add",
            "-b",
            "integration-selftest",
            str(isolated),
            primary_sha,
        ],
        cwd=repo,
    )
    run(
        [
            sys.executable,
            str(fixture_dir / "apply_reference.py"),
            "--repo",
            str(isolated),
        ]
    )
    run(
        [
            sys.executable,
            str(fixture_dir / "verify.py"),
            "--repo",
            str(isolated),
        ]
    )

    writer = subprocess.Popen(
        [
            sys.executable,
            str(fixture_dir / "hold_writer.py"),
            "--repo",
            str(repo),
            "--state",
            str(state),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ready = state / "writer-ready.json"
    release = state / "release-writer"
    stopped = state / "writer-stopped.json"
    try:
        wait_for(ready)
        run(
            [
                sys.executable,
                str(fixture_dir / "integrate_worktree.py"),
                "--source",
                str(isolated),
                "--target",
                str(repo),
                "--expected-base",
                primary_sha,
                "--writer-stopped-marker",
                str(stopped),
                "--manifest",
                str(root / "premature-integration.json"),
            ],
            expect_success=False,
        )
        if (root / "premature-integration.json").exists():
            raise SystemExit("premature integration unexpectedly wrote a manifest")

        release.touch()
        try:
            writer_output, _ = writer.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            writer.kill()
            writer_output, _ = writer.communicate()
            raise SystemExit("active writer did not stop after release")
        print(writer_output, end="")
        if writer.returncode != 0:
            raise SystemExit(f"active writer exited {writer.returncode}")
        wait_for(stopped)
    finally:
        if writer.poll() is None:
            release.touch(exist_ok=True)
            writer.kill()
            writer.wait()

    integration_manifest = root / "integration-manifest.json"
    run(
        [
            sys.executable,
            str(fixture_dir / "integrate_worktree.py"),
            "--source",
            str(isolated),
            "--target",
            str(repo),
            "--expected-base",
            primary_sha,
            "--writer-stopped-marker",
            str(stopped),
            "--manifest",
            str(integration_manifest),
        ]
    )
    run(
        [
            sys.executable,
            str(fixture_dir / "verify.py"),
            "--repo",
            str(repo),
        ]
    )
    integration = json.loads(integration_manifest.read_text(encoding="utf-8"))
    if integration["target_worktree"] != str(repo.resolve()):
        raise SystemExit("integration manifest does not identify the primary target")
    if integration["commit_created"]:
        raise SystemExit("integration helper must not create a commit")
    print("isolated worktree integration self-test passed")

    barrier_name = "selftest"
    barrier = subprocess.Popen(
        [
            sys.executable,
            str(fixture_dir / "thread_barrier.py"),
            "--state",
            str(state),
            "--name",
            barrier_name,
            "--timeout-seconds",
            "30",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    barrier_ready = state / f"{barrier_name}-ready.json"
    barrier_release = state / f"{barrier_name}-release"
    barrier_released = state / f"{barrier_name}-released.json"
    try:
        wait_for(barrier_ready)
        if barrier.poll() is not None:
            raise SystemExit("barrier terminated before controller release")
        barrier_release.touch()
        barrier_output, _ = barrier.communicate(timeout=30)
        print(barrier_output, end="")
        if barrier.returncode != 0:
            raise SystemExit(f"barrier exited {barrier.returncode}")
        wait_for(barrier_released)
    finally:
        if barrier.poll() is None:
            barrier_release.touch(exist_ok=True)
            barrier.kill()
            barrier.wait()
    print("thread barrier self-test passed")

    run([sys.executable, str(fixture_dir / "teardown.py"), "--root", str(root)])
    print("durable-thread fixture v5 self-test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
