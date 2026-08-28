#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def git(repo: Path, *args: str) -> str:
    return run(["git", *args], cwd=repo)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(path).encode("utf-8"))
        else:
            digest.update(b"file\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=True).samefile(right.resolve(strict=True))
    except OSError:
        return False


def link_record(link: Path, expected: Path) -> dict[str, Any]:
    if not link.is_symlink():
        raise SystemExit(f"expected symlink is missing: {link}")
    resolved = link.resolve(strict=True)
    if not same_path(resolved, expected):
        raise SystemExit(
            f"installed link mismatch: {link} -> {resolved}; expected {expected}"
        )
    return {
        "path": str(link),
        "link_text": os.readlink(link),
        "resolved_target": str(resolved),
        "expected_target": str(expected.resolve(strict=True)),
    }


def ensure_outside(path: Path, directory: Path, label: str) -> None:
    resolved_path = path.resolve(strict=False)
    resolved_directory = directory.resolve(strict=True)
    if resolved_path == resolved_directory or resolved_directory in resolved_path.parents:
        raise SystemExit(f"{label} must be outside source repository: {resolved_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an exact detached policy checkout, install it into a fresh "
            "Codex home, and record verifiable root/skill identity."
        )
    )
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--policy-commit", required=True)
    parser.add_argument(
        "--policy-side",
        required=True,
        choices=("baseline", "candidate"),
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_repo = Path(
        git(args.source_repo.expanduser().resolve(), "rev-parse", "--show-toplevel")
    ).resolve()
    run_dir = args.run_dir.expanduser().resolve(strict=False)
    ensure_outside(run_dir, source_repo, "policy run directory")

    policy_checkout = run_dir / "policy-checkout"
    codex_home = run_dir / "codex-home"
    manifest_path = run_dir / "policy-load-manifest.json"
    for path in (policy_checkout, codex_home, manifest_path):
        if path.exists() or path.is_symlink():
            raise SystemExit(f"refusing to reuse policy state: {path}")
    run_dir.mkdir(parents=True, exist_ok=False)

    resolved_commit = git(
        source_repo,
        "rev-parse",
        "--verify",
        f"{args.policy_commit}^{{commit}}",
    )
    run(
        [
            "git",
            "clone",
            "--no-checkout",
            "--no-hardlinks",
            str(source_repo),
            str(policy_checkout),
        ]
    )
    git(policy_checkout, "checkout", "--detach", resolved_commit)

    actual_commit = git(policy_checkout, "rev-parse", "HEAD")
    if actual_commit != resolved_commit:
        raise SystemExit(
            f"policy checkout mismatch: expected {resolved_commit}, got {actual_commit}"
        )
    checkout_status = git(policy_checkout, "status", "--porcelain")
    if checkout_status:
        raise SystemExit(f"policy checkout is not clean:\n{checkout_status}")

    installer = policy_checkout / "scripts" / "install_codex.py"
    installer_command = [
        sys.executable,
        str(installer),
        "--root",
        str(policy_checkout),
        "--codex-home",
        str(codex_home),
    ]
    installer_output = run(installer_command)

    agents_source = policy_checkout / "AGENTS.md"
    skill_source = policy_checkout / "skills" / "software-engineering"
    skill_entrypoint = skill_source / "SKILL.md"
    interface_file = skill_source / "agents" / "openai.yaml"

    kit_link = codex_home / "davis-agent-kit"
    agents_link = codex_home / "AGENTS.md"
    skill_link = codex_home / "skills" / "software-engineering"

    links = {
        "kit": link_record(kit_link, policy_checkout),
        "agents": link_record(agents_link, agents_source),
        "software_engineering": link_record(skill_link, skill_source),
    }

    identities = {
        "root_agents": {
            "git_blob_oid": git(policy_checkout, "rev-parse", "HEAD:AGENTS.md"),
            "sha256": sha256_file(agents_source),
            "installed_sha256": sha256_file(agents_link.resolve(strict=True)),
        },
        "software_engineering_tree": {
            "git_tree_oid": git(
                policy_checkout,
                "rev-parse",
                "HEAD:skills/software-engineering",
            ),
            "sha256": sha256_tree(skill_source),
            "installed_sha256": sha256_tree(skill_link.resolve(strict=True)),
        },
        "software_engineering_entrypoint": {
            "git_blob_oid": git(
                policy_checkout,
                "rev-parse",
                "HEAD:skills/software-engineering/SKILL.md",
            ),
            "sha256": sha256_file(skill_entrypoint),
            "installed_sha256": sha256_file(
                skill_link.resolve(strict=True) / "SKILL.md"
            ),
        },
        "software_engineering_interface": {
            "git_blob_oid": git(
                policy_checkout,
                "rev-parse",
                "HEAD:skills/software-engineering/agents/openai.yaml",
            ),
            "sha256": sha256_file(interface_file),
            "installed_sha256": sha256_file(
                skill_link.resolve(strict=True) / "agents" / "openai.yaml"
            ),
        },
    }
    for name, identity in identities.items():
        if identity["sha256"] != identity["installed_sha256"]:
            raise SystemExit(f"installed identity mismatch: {name}")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "policy_side": args.policy_side,
        "requested_commit": args.policy_commit,
        "resolved_commit": resolved_commit,
        "actual_checkout_commit": actual_commit,
        "source_repository": str(source_repo),
        "policy_checkout": str(policy_checkout),
        "codex_home": str(codex_home),
        "checkout_status": checkout_status,
        "installer_command": installer_command,
        "installer_output": installer_output,
        "links": links,
        "identities": identities,
        "session_launch_contract": {
            "environment": {"CODEX_HOME": str(codex_home)},
            "fresh_process_required": True,
            "fresh_root_and_model_context_required": True,
            "start_only_after_manifest_verification": True,
            "boot_attestation": {
                "checkout_commit": resolved_commit,
                "agents_sha256": identities["root_agents"]["sha256"],
                "skill_tree_sha256": identities["software_engineering_tree"][
                    "sha256"
                ],
                "skill_entrypoint_sha256": identities[
                    "software_engineering_entrypoint"
                ]["sha256"],
                "interface_sha256": identities[
                    "software_engineering_interface"
                ]["sha256"],
            },
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
