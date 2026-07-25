#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import subprocess
import sys

from kit_manifest import ManifestError, load_manifest, validate_manifest


DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Davis Agent Kit links into a Codex home."
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
        help="Codex home to install into (default: CODEX_HOME or ~/.codex)",
    )
    return parser.parse_args()


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _is_expected_link(path: Path, expected: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        return path.resolve(strict=True).samefile(expected.resolve(strict=True))
    except (OSError, RuntimeError):
        return False


def _nearest_existing_path(path: Path) -> Path | None:
    candidate = path
    while not _path_exists(candidate):
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate


def _path_is_within(path: Path, directory: Path) -> bool:
    existing_path = _nearest_existing_path(path)
    if existing_path is None:
        return False
    try:
        resolved_path = existing_path.resolve(strict=True)
        resolved_directory = directory.resolve(strict=True)
    except (OSError, RuntimeError):
        return False

    for candidate in (resolved_path, *resolved_path.parents):
        try:
            if candidate.samefile(resolved_directory):
                return True
        except OSError:
            continue
    return False


def _path_is_lexically_within(path: Path, directory: Path) -> bool:
    normalized_path = Path(os.path.abspath(os.path.normpath(path)))
    normalized_directory = Path(os.path.abspath(os.path.normpath(directory)))
    return (
        normalized_path == normalized_directory
        or normalized_directory in normalized_path.parents
    )


def _is_direct_checkout(kit_path: Path, repo_root: Path) -> bool:
    if kit_path.is_symlink() or not kit_path.is_dir():
        return False
    try:
        return kit_path.samefile(repo_root)
    except OSError:
        return False


def _symlink_target(path: Path) -> Path:
    target = path.readlink()
    return target if target.is_absolute() else path.parent / target


@dataclass
class InstallResult:
    messages: list[str] = field(default_factory=list)
    created_links: list[Path] = field(default_factory=list)
    created_directories: list[Path] = field(default_factory=list)

    def rollback(self) -> list[str]:
        errors: list[str] = []
        for path in reversed(self.created_links):
            try:
                if path.is_symlink():
                    path.unlink()
                elif path.exists():
                    errors.append(f"cannot remove unexpected path: {path}")
            except OSError as exc:
                errors.append(f"cannot remove created link {path}: {exc}")

        for directory in reversed(self.created_directories):
            try:
                directory.rmdir()
            except FileNotFoundError:
                pass
            except OSError as exc:
                errors.append(f"cannot remove created directory {directory}: {exc}")
        return errors


def _reject_unsafe_topology(
    repo_root: Path,
    codex_home: Path,
    skills_home: Path,
    direct_checkout: bool,
) -> None:
    if _path_is_within(codex_home, repo_root):
        raise ManifestError(
            f"Codex home is inside the checkout: {codex_home}. "
            "Choose a Codex home outside the checkout; "
            "no installation paths were changed."
        )
    if (
        not direct_checkout
        and codex_home.is_dir()
        and _path_is_within(repo_root, codex_home)
    ):
        raise ManifestError(
            f"checkout is nested under Codex home: {repo_root}. "
            "Move it outside Codex home or use the managed kit path itself; "
            "no installation paths were changed."
        )
    if skills_home.is_symlink():
        raise ManifestError(
            f"Codex skills root is a whole-directory symlink: {skills_home}. "
            "Replace it with a real directory; no installation paths were changed."
        )
    if skills_home.exists() and not skills_home.is_dir():
        raise ManifestError(
            f"Codex skills root is not a directory: {skills_home}. "
            "Resolve the conflict manually; no installation paths were changed."
        )
    if _path_is_within(skills_home, repo_root):
        raise ManifestError(
            f"Codex skills root resolves inside the checkout: {skills_home}. "
            "Choose a skills root outside the checkout; "
            "no installation paths were changed."
        )


def _preflight_link(path: Path, expected: Path, label: str) -> bool:
    if not _path_exists(path):
        return True
    if _is_expected_link(path, expected):
        return False
    raise ManifestError(
        f"{label} already exists and is not the expected link: {path}. "
        "Back up or remove it manually, then rerun; "
        "no installation paths were changed."
    )


def install(repo_root: Path, codex_home: Path) -> InstallResult:
    manifest = load_manifest(repo_root)
    errors = validate_manifest(manifest, repo_root)
    if errors:
        raise ManifestError("\n".join(errors))

    kit_path = codex_home / manifest.install.kit_link
    skills_home = codex_home / manifest.install.skills_dir
    direct_checkout = _is_direct_checkout(kit_path, repo_root)
    _reject_unsafe_topology(
        repo_root,
        codex_home,
        skills_home,
        direct_checkout,
    )

    result = InstallResult()
    desired_links = [
        (
            codex_home / manifest.install.agents_link,
            kit_path / manifest.normative_source,
            "global AGENTS.md",
        ),
        *(
            (
                skills_home / skill.name,
                kit_path / skill.path,
                f"skill {skill.name}",
            )
            for skill in manifest.skills
        ),
    ]
    if direct_checkout:
        result.messages.append(f"KEEP {kit_path} (checkout)")
    else:
        desired_links.insert(0, (kit_path, repo_root, "kit path"))

    links_to_create: list[tuple[Path, Path]] = []
    for path, target, label in desired_links:
        if _preflight_link(path, target, label):
            links_to_create.append((path, target))
        else:
            result.messages.append(f"KEEP {path}")

    for retired_name in manifest.install.retired_skills:
        retired_path = skills_home / retired_name
        if _path_exists(retired_path):
            raise ManifestError(
                f"Retired skill still exists: {retired_path}. Remove it manually, "
                "then rerun; no installation paths were changed."
            )

    active_names = {skill.name for skill in manifest.skills}
    retired_names = set(manifest.install.retired_skills)
    if skills_home.is_dir():
        for installed_path in skills_home.iterdir():
            if installed_path.name in active_names | retired_names:
                continue
            if (
                installed_path.is_symlink()
                and (
                    _path_is_within(_symlink_target(installed_path), repo_root)
                    or _path_is_lexically_within(
                        _symlink_target(installed_path),
                        kit_path,
                    )
                )
            ):
                raise ManifestError(
                    f"Unlisted skill link points into this kit: {installed_path}. "
                    "Remove it manually, then rerun; "
                    "no installation paths were changed."
                )

    try:
        if not codex_home.exists():
            codex_home.mkdir(parents=True)
            result.created_directories.append(codex_home)
        if not skills_home.exists():
            skills_home.mkdir(parents=True)
            result.created_directories.append(skills_home)
        for path, target in links_to_create:
            path.symlink_to(target, target_is_directory=target.is_dir())
            result.created_links.append(path)
            result.messages.append(f"LINK {path} -> {target}")
    except (OSError, RuntimeError) as exc:
        rollback_errors = result.rollback()
        rollback_note = (
            f" Rollback was incomplete: {'; '.join(rollback_errors)}."
            if rollback_errors
            else " Created installation paths were rolled back."
        )
        raise ManifestError(f"{exc}.{rollback_note}") from exc

    return result


def run_doctor(repo_root: Path, codex_home: Path) -> int:
    completed = subprocess.run(
        (
            sys.executable,
            str(repo_root / "scripts" / "doctor.py"),
            "--root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ),
        check=False,
    )
    return completed.returncode


def _report_post_install_failure(
    result: InstallResult,
    reason: object,
) -> None:
    rollback_errors = result.rollback()
    rollback_note = (
        f" Rollback was incomplete: {'; '.join(rollback_errors)}."
        if rollback_errors
        else " Created installation paths were rolled back."
    )
    try:
        print(f"Install failed: {reason}.{rollback_note}", file=sys.stderr)
    except OSError:
        pass


def _silence_broken_stdout() -> None:
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull_fd, sys.stdout.fileno())
        finally:
            os.close(devnull_fd)
    except (OSError, ValueError):
        pass


def main() -> int:
    args = parse_args()
    repo_root = args.root.expanduser().resolve()
    codex_home = args.codex_home.expanduser().resolve(strict=False)

    try:
        result = install(repo_root, codex_home)
    except (ManifestError, OSError, RuntimeError) as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        return 1

    try:
        for message in result.messages:
            print(message)
        sys.stdout.flush()
        doctor_status = run_doctor(repo_root, codex_home)
    except BrokenPipeError as exc:
        _report_post_install_failure(result, exc)
        _silence_broken_stdout()
        return 1
    except KeyboardInterrupt as exc:
        _report_post_install_failure(result, exc)
        return 130
    except (OSError, RuntimeError) as exc:
        _report_post_install_failure(result, exc)
        return 1

    if doctor_status != 0:
        _report_post_install_failure(
            result,
            f"doctor exited with status {doctor_status}",
        )
        return doctor_status

    try:
        print("Codex installation is ready. Restart Codex or start a new session.")
        sys.stdout.flush()
    except BrokenPipeError:
        _silence_broken_stdout()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
