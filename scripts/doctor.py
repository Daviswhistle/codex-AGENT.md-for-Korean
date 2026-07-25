#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from kit_manifest import ManifestError, KitManifest, load_manifest, validate_manifest


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
Level = Literal["PASS", "WARN", "FAIL", "INFO"]


@dataclass(frozen=True)
class Result:
    level: Level
    code: str
    message: str


def run_git(repo_root: Path, *args: str) -> tuple[int, str]:
    completed = subprocess.run(
        ("git", "-C", str(repo_root), *args),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return completed.returncode, completed.stdout.strip()


def sanitize_git_remote(remote: str) -> str:
    remote = remote.strip().split("#", 1)[0].split("?", 1)[0]
    if "://" in remote:
        parsed = urlsplit(remote)
        netloc = parsed.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    if "@" in remote:
        return remote.split("@", 1)[1]
    return remote


def repository_checks(repo_root: Path, manifest: KitManifest) -> list[Result]:
    results: list[Result] = []
    manifest_errors = validate_manifest(manifest, repo_root)
    if manifest_errors:
        results.extend(Result("FAIL", "manifest", error) for error in manifest_errors)
    else:
        results.append(
            Result(
                "PASS",
                "manifest",
                f"kit {manifest.kit_version}, schema {manifest.schema_version}, "
                f"{len(manifest.skills)} skills",
            )
        )

    current_python = sys.version_info[:2]
    if current_python >= manifest.minimum_python:
        results.append(
            Result(
                "PASS",
                "python",
                f"Python {current_python[0]}.{current_python[1]} satisfies "
                f">= {manifest.minimum_python_text}",
            )
        )
    else:
        results.append(
            Result(
                "FAIL",
                "python",
                f"Python {current_python[0]}.{current_python[1]} is below "
                f"{manifest.minimum_python_text}",
            )
        )

    if shutil.which("git") is None:
        results.append(
            Result("WARN", "git", "git is unavailable; checkout version and drift are unknown")
        )
        return results

    code, top = run_git(repo_root, "rev-parse", "--show-toplevel")
    if code != 0:
        results.append(
            Result("WARN", "git", "repository is not a git checkout; update drift is unknown")
        )
        return results

    try:
        git_root_matches = Path(top).samefile(repo_root)
    except OSError:
        git_root_matches = False
    if not git_root_matches:
        results.append(
            Result("FAIL", "git-root", f"git root is {top}, expected {repo_root}")
        )
    else:
        results.append(Result("PASS", "git-root", f"git checkout: {top}"))

    code, head = run_git(repo_root, "rev-parse", "--short=12", "HEAD")
    if code == 0:
        results.append(Result("INFO", "git-head", f"HEAD {head}"))

    code, branch = run_git(repo_root, "branch", "--show-current")
    if code == 0:
        results.append(Result("INFO", "git-branch", branch or "detached HEAD"))

    code, status = run_git(repo_root, "status", "--porcelain")
    if code == 0:
        if status:
            changed = len(status.splitlines())
            results.append(
                Result("WARN", "git-dirty", f"working tree has {changed} changed path(s)")
            )
        else:
            results.append(Result("PASS", "git-clean", "working tree is clean"))

    code, remote = run_git(repo_root, "remote", "get-url", "origin")
    if code == 0:
        results.append(Result("INFO", "git-origin", sanitize_git_remote(remote)))
    else:
        results.append(Result("WARN", "git-origin", "origin remote is not configured"))

    return results


def _check_symlink(path: Path, expected: Path, code: str) -> list[Result]:
    if not path.exists() and not path.is_symlink():
        return [Result("FAIL", code, f"missing symlink: {path}")]
    if not path.is_symlink():
        return [Result("FAIL", code, f"expected a symlink, found a regular path: {path}")]

    try:
        actual = path.resolve(strict=True)
        target = expected.resolve(strict=True)
        same_target = actual.samefile(target)
    except (OSError, RuntimeError) as exc:
        return [Result("FAIL", code, f"cannot resolve {path}: {exc}")]

    if not same_target:
        return [
            Result(
                "FAIL",
                code,
                f"{path} resolves to {actual}; expected {target}",
            )
        ]
    return [Result("PASS", code, f"{path} -> {target}")]


def _check_kit_path(path: Path, expected: Path) -> list[Result]:
    if path.is_dir() and not path.is_symlink():
        try:
            same_directory = path.samefile(expected)
        except OSError:
            same_directory = False
        if same_directory:
            return [Result("PASS", "kit-link", f"checkout directory: {path}")]
    return _check_symlink(path, expected, "kit-link")


def installation_checks(
    repo_root: Path, manifest: KitManifest, codex_home: Path
) -> list[Result]:
    results: list[Result] = []
    if not codex_home.exists():
        return [Result("FAIL", "codex-home", f"Codex home does not exist: {codex_home}")]
    if not codex_home.is_dir():
        return [Result("FAIL", "codex-home", f"Codex home is not a directory: {codex_home}")]
    results.append(Result("PASS", "codex-home", str(codex_home)))

    kit_link = codex_home / manifest.install.kit_link
    results.extend(_check_kit_path(kit_link, repo_root))

    agents_link = codex_home / manifest.install.agents_link
    normative_source = repo_root / manifest.normative_source
    results.extend(_check_symlink(agents_link, normative_source, "agents-link"))

    installed_skills_root = codex_home / manifest.install.skills_dir
    if not installed_skills_root.is_dir():
        results.append(
            Result(
                "FAIL",
                "skills-root",
                f"installed skills directory is missing: {installed_skills_root}",
            )
        )
        return results
    results.append(Result("PASS", "skills-root", str(installed_skills_root)))

    active_skill_names = {skill.name for skill in manifest.skills}
    for skill in manifest.skills:
        link = installed_skills_root / skill.name
        expected = skill.root(repo_root)
        results.extend(_check_symlink(link, expected, f"skill-link:{skill.name}"))
        entrypoint = link / skill.entrypoint
        if entrypoint.is_file():
            results.append(
                Result(
                    "PASS",
                    f"skill-entrypoint:{skill.name}",
                    str(entrypoint),
                )
            )
        else:
            results.append(
                Result(
                    "FAIL",
                    f"skill-entrypoint:{skill.name}",
                    f"Codex load entrypoint is missing: {entrypoint}",
                )
            )

    retired_skill_names = set(manifest.install.retired_skills)
    for retired_name in manifest.install.retired_skills:
        retired_path = installed_skills_root / retired_name
        if retired_path.exists() or retired_path.is_symlink():
            results.append(
                Result(
                    "FAIL",
                    f"retired-skill:{retired_name}",
                    f"retired kit skill is still installed: {retired_path}",
                )
            )
        else:
            results.append(
                Result(
                    "PASS",
                    f"retired-skill:{retired_name}",
                    f"not installed: {retired_path}",
                )
            )

    try:
        installed_paths = tuple(installed_skills_root.iterdir())
    except OSError as exc:
        results.append(
            Result(
                "FAIL",
                "skills-root-read",
                f"cannot inspect installed skills directory: {exc}",
            )
        )
        installed_paths = ()

    for installed_path in installed_paths:
        if installed_path.name in active_skill_names | retired_skill_names:
            continue
        if not installed_path.is_symlink():
            continue
        target = installed_path.resolve(strict=False)
        try:
            target.relative_to(repo_root)
        except ValueError:
            continue
        results.append(
            Result(
                "WARN",
                f"unlisted-kit-skill:{installed_path.name}",
                f"unlisted skill link points into this kit: {installed_path} -> {target}",
            )
        )

    load_issues = any(result.level in {"WARN", "FAIL"} for result in results)
    reload_message = (
        "fix the reported filesystem load-surface issues before restarting Codex"
        if load_issues
        else "filesystem load surfaces are correct; restart Codex or start a new session after changes"
    )
    results.append(Result("INFO", "runtime-reload", reload_message))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the Davis Agent Kit checkout and Codex installation links."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME") or "~/.codex"),
        help="Codex home to inspect (default: CODEX_HOME or ~/.codex)",
    )
    parser.add_argument(
        "--repo-only",
        action="store_true",
        help="check repository and manifest without requiring a Codex installation",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero when warnings are present",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.root.expanduser().resolve()

    try:
        manifest = load_manifest(repo_root)
    except ManifestError as exc:
        results = [Result("FAIL", "manifest", str(exc))]
        manifest = None
    else:
        results = repository_checks(repo_root, manifest)
        if not args.repo_only:
            codex_home = args.codex_home.expanduser().resolve(strict=False)
            results.extend(installation_checks(repo_root, manifest, codex_home))

    counts = {level: 0 for level in ("PASS", "WARN", "FAIL", "INFO")}
    for result in results:
        counts[result.level] += 1

    failed = counts["FAIL"] > 0 or (args.strict and counts["WARN"] > 0)
    if args.json:
        payload = {
            "ok": not failed,
            "strict": args.strict,
            "repo_only": args.repo_only,
            "kit_version": manifest.kit_version if manifest else None,
            "schema_version": manifest.schema_version if manifest else None,
            "results": [asdict(result) for result in results],
            "summary": counts,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(f"[{result.level}] {result.code}: {result.message}")
        print(
            "\nDoctor summary: "
            + ", ".join(f"{counts[level]} {level.lower()}" for level in counts)
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
