#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"(?m)^name:\s*['\"]?([A-Za-z0-9._-]+)['\"]?\s*$")
DESCRIPTION_RE = re.compile(r"(?m)^description:\s*(.+)$")
RESOURCE_RE = re.compile(r"`((?:references|agents|scripts)/[^`\s]+)")


@dataclass(frozen=True)
class CommandCheck:
    name: str
    command: tuple[str, ...]


def validate_skills(repo_root: Path) -> list[str]:
    errors = []
    skill_files = sorted((repo_root / "skills").glob("*/SKILL.md"))
    if not skill_files:
        return ["no skills found"]

    for skill_file in skill_files:
        text = skill_file.read_text(encoding="utf-8")
        expected = skill_file.parent.name
        name_match = NAME_RE.search(text)
        if not name_match or name_match.group(1) != expected:
            errors.append(f"{skill_file}: frontmatter name must be {expected!r}")
        description_match = DESCRIPTION_RE.search(text)
        if not description_match:
            errors.append(f"{skill_file}: missing description")
        for document in [skill_file, *skill_file.parent.rglob("*.md")]:
            current = text if document == skill_file else document.read_text(encoding="utf-8")
            for raw in RESOURCE_RE.findall(current):
                value = raw.rstrip(".,:;)]}")
                if "<" in value or ">" in value:
                    continue
                if ".." in Path(value).parts:
                    errors.append(f"{document}: unsafe resource reference {value}")
                    continue
                if not (skill_file.parent / value).exists():
                    errors.append(f"{document}: missing resource {value}")
    return errors


def discover_test_suites(repo_root: Path) -> list[CommandCheck]:
    dirs = [repo_root / "tests", *sorted(repo_root.glob("skills/*/tests"))]
    checks = []
    for test_dir in dirs:
        if test_dir.is_dir() and any(test_dir.glob("test*.py")):
            rel = test_dir.relative_to(repo_root).as_posix()
            checks.append(CommandCheck(
                f"unittest:{rel}",
                (sys.executable, "-m", "unittest", "discover", "-s", rel, "-p", "test*.py", "-v"),
            ))
    return checks


def discover_helper_smoke_checks(repo_root: Path) -> list[CommandCheck]:
    return [
        CommandCheck(
            f"helper-help:{script.relative_to(repo_root).as_posix()}",
            (sys.executable, script.relative_to(repo_root).as_posix(), "--help"),
        )
        for script in sorted(repo_root.glob("skills/*/scripts/*.py"))
    ]


def run_check(check: CommandCheck, repo_root: Path, quiet: bool) -> bool:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate active Davis Agent Kit contracts.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--skip-helper-smoke", action="store_true")
    args = parser.parse_args()
    repo_root = args.root.expanduser().resolve()

    if not (repo_root / "AGENTS.md").is_file():
        print("[FAIL] missing AGENTS.md")
        return 1

    errors = validate_skills(repo_root)
    if errors:
        print("[FAIL] skill validation")
        for error in errors:
            print(f"  - {error}")
        return 1

    checks = discover_test_suites(repo_root)
    if not args.skip_helper_smoke:
        checks.extend(discover_helper_smoke_checks(repo_root))

    failed = [check.name for check in checks if not run_check(check, repo_root, args.quiet)]
    print(f"Validation summary: {len(checks)-len(failed)} passed, {len(failed)} failed, {len(checks)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
