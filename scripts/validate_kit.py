#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from kit_manifest import ManifestError, load_manifest, validate_manifest


DEFAULT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CommandCheck:
    name: str
    command: tuple[str, ...]


def discover_test_suites(repo_root: Path) -> list[CommandCheck]:
    test_dirs = [repo_root / "tests"]
    test_dirs.extend(sorted(repo_root.glob("skills/*/tests")))

    suites: list[CommandCheck] = []
    for test_dir in test_dirs:
        if not test_dir.is_dir() or not any(test_dir.glob("test*.py")):
            continue
        rel = test_dir.relative_to(repo_root).as_posix()
        suites.append(
            CommandCheck(
                name=f"unittest:{rel}",
                command=(
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    rel,
                    "-p",
                    "test*.py",
                    "-v",
                ),
            )
        )
    return suites


def discover_helper_smoke_checks(repo_root: Path) -> list[CommandCheck]:
    checks: list[CommandCheck] = []
    for script in sorted(repo_root.glob("skills/*/scripts/*.py")):
        rel = script.relative_to(repo_root).as_posix()
        checks.append(
            CommandCheck(
                name=f"helper-help:{rel}",
                command=(sys.executable, rel, "--help"),
            )
        )
    return checks


def run_check(check: CommandCheck, repo_root: Path, quiet: bool) -> bool:
    if not quiet:
        print(f"\n==> {check.name}", flush=True)
        print("    " + " ".join(check.command), flush=True)

    completed = subprocess.run(
        check.command,
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE if quiet or check.name.startswith("helper-help:") else None,
        stderr=subprocess.STDOUT if quiet or check.name.startswith("helper-help:") else None,
        check=False,
    )
    if completed.returncode == 0:
        if not quiet:
            print(f"[PASS] {check.name}")
        return True

    print(f"[FAIL] {check.name} (exit {completed.returncode})")
    if completed.stdout:
        print(completed.stdout.rstrip())
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run manifest validation, executable tests, and helper smoke checks."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument("--quiet", action="store_true", help="show only failures and summary")
    parser.add_argument(
        "--skip-helper-smoke",
        action="store_true",
        help="skip invoking each bundled helper with --help",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.root.expanduser().resolve()

    try:
        manifest = load_manifest(repo_root)
    except ManifestError as exc:
        print(f"[FAIL] manifest: {exc}")
        return 1

    manifest_errors = validate_manifest(manifest, repo_root)
    if manifest_errors:
        print("[FAIL] manifest validation")
        for error in manifest_errors:
            print(f"  - {error}")
        return 1

    if not args.quiet:
        print(
            f"[PASS] manifest validation "
            f"(kit {manifest.kit_version}, schema {manifest.schema_version})",
            flush=True,
        )

    checks = discover_test_suites(repo_root)
    if not args.skip_helper_smoke:
        checks.extend(discover_helper_smoke_checks(repo_root))

    failed: list[str] = []
    for check in checks:
        if not run_check(check, repo_root, args.quiet):
            failed.append(check.name)

    print(
        f"\nValidation summary: {len(checks) - len(failed)} passed, "
        f"{len(failed)} failed, {len(checks)} total"
    )
    if failed:
        print("Failed checks:")
        for name in failed:
            print(f"  - {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
