from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from doctor import sanitize_git_remote  # noqa: E402
from install_codex import install  # noqa: E402
from kit_manifest import ManifestError, load_manifest, validate_manifest  # noqa: E402
from validate_kit import discover_helper_smoke_checks, discover_test_suites  # noqa: E402


class ManifestAndValidationTests(unittest.TestCase):
    def test_repository_manifest_is_valid(self) -> None:
        manifest = load_manifest(ROOT)

        self.assertEqual(validate_manifest(manifest, ROOT), [])
        self.assertTrue((ROOT / manifest.normative_source).is_file())
        self.assertGreater(len(manifest.skills), 0)

    def test_manifest_rejects_missing_and_unsafe_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# Test\n", encoding="utf-8")
            skill = root / "skills" / "listed"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: listed\n"
                "description: Test skill.\n"
                "---\n\n"
                "Read `references/missing.md` and `references/../escape.md`.\n",
                encoding="utf-8",
            )
            (root / "kit.toml").write_text(
                'schema_version = 1\n'
                'kit_version = "0.1.0"\n'
                'minimum_python = "3.11"\n'
                'normative_source = "AGENTS.md"\n\n'
                '[install]\n'
                'kit_link = "kit"\n'
                'agents_link = "AGENTS.md"\n'
                'skills_dir = "installed-skills"\n'
                'retired_skills = []\n\n'
                '[[skills]]\n'
                'name = "listed"\n'
                'path = "skills/listed"\n'
                'entrypoint = "SKILL.md"\n',
                encoding="utf-8",
            )

            errors = validate_manifest(load_manifest(root), root)

        joined = "\n".join(errors)
        self.assertIn("missing resource referenced", joined)
        self.assertIn("unsafe resource referenced", joined)

    def test_validation_runner_discovers_executable_suites_and_helpers(self) -> None:
        suite_names = {check.name for check in discover_test_suites(ROOT)}
        expected_test_dirs = {
            path.relative_to(ROOT).as_posix()
            for path in [ROOT / "tests", *sorted(ROOT.glob("skills/*/tests"))]
            if path.is_dir() and any(path.glob("test*.py"))
        }
        self.assertEqual(
            suite_names,
            {f"unittest:{path}" for path in expected_test_dirs},
        )

        helper_names = {check.name for check in discover_helper_smoke_checks(ROOT)}
        expected_helpers = {
            f"helper-help:{path.relative_to(ROOT).as_posix()}"
            for path in ROOT.glob("skills/*/scripts/*.py")
        }
        self.assertEqual(helper_names, expected_helpers)


@unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
class InstallerAndDoctorTests(unittest.TestCase):
    def test_installer_is_idempotent(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"

            first = install(ROOT, codex_home)
            second = install(ROOT, codex_home)

            self.assertGreater(len(first.created_links), 0)
            self.assertEqual(second.created_links, [])
            self.assertFalse(any(message.startswith("LINK ") for message in second.messages))
            self.assertEqual(
                (codex_home / manifest.install.kit_link).resolve(strict=True),
                ROOT.resolve(),
            )
            self.assertEqual(
                (codex_home / manifest.install.agents_link).resolve(strict=True),
                (ROOT / manifest.normative_source).resolve(),
            )
            for skill in manifest.skills:
                self.assertEqual(
                    (
                        codex_home
                        / manifest.install.skills_dir
                        / skill.name
                    ).resolve(strict=True),
                    skill.root(ROOT).resolve(),
                )

    def test_installer_refuses_existing_conflict_before_mutation(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            agents_path = codex_home / manifest.install.agents_link
            agents_path.write_text("keep me\n", encoding="utf-8")

            with self.assertRaises(ManifestError):
                install(ROOT, codex_home)

            self.assertEqual(agents_path.read_text(encoding="utf-8"), "keep me\n")
            self.assertFalse(
                (codex_home / manifest.install.kit_link).exists()
                or (codex_home / manifest.install.kit_link).is_symlink()
            )
            self.assertFalse((codex_home / manifest.install.skills_dir).exists())

    def test_installer_rolls_back_partial_link_failure(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            failing_path = (
                codex_home
                / manifest.install.skills_dir
                / manifest.skills[0].name
            )
            original_symlink_to = Path.symlink_to

            def fail_first_skill_link(
                path: Path,
                target: Path,
                target_is_directory: bool = False,
            ) -> None:
                if path == failing_path:
                    raise PermissionError("simulated link failure")
                original_symlink_to(
                    path,
                    target,
                    target_is_directory=target_is_directory,
                )

            with mock.patch.object(Path, "symlink_to", new=fail_first_skill_link):
                with self.assertRaises(ManifestError) as raised:
                    install(ROOT, codex_home)

            self.assertIn("simulated link failure", str(raised.exception))
            self.assertFalse(codex_home.exists())

    def test_installer_rejects_whole_skills_root_symlink(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            codex_home = temp_root / ".codex"
            external_skills = temp_root / "external-skills"
            codex_home.mkdir()
            external_skills.mkdir()
            skills_home = codex_home / manifest.install.skills_dir
            skills_home.symlink_to(external_skills, target_is_directory=True)

            with self.assertRaises(ManifestError) as raised:
                install(ROOT, codex_home)

            self.assertIn("whole-directory symlink", str(raised.exception))
            self.assertTrue(skills_home.is_symlink())
            self.assertFalse((codex_home / manifest.install.kit_link).exists())
            self.assertFalse((codex_home / manifest.install.agents_link).exists())

    def test_doctor_accepts_exact_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            install(ROOT, codex_home)

            completed = subprocess.run(
                (
                    sys.executable,
                    str(ROOT / "scripts" / "doctor.py"),
                    "--root",
                    str(ROOT),
                    "--codex-home",
                    str(codex_home),
                    "--json",
                ),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        by_code = {result["code"]: result for result in payload["results"]}
        self.assertEqual(by_code["kit-link"]["level"], "PASS")
        self.assertEqual(by_code["agents-link"]["level"], "PASS")


class DoctorUtilityTests(unittest.TestCase):
    def test_git_remote_sanitization_removes_credentials_and_query_data(self) -> None:
        self.assertEqual(
            sanitize_git_remote(
                "https://user:secret@github.com/owner/repo.git?token=x#fragment"
            ),
            "https://github.com/owner/repo.git",
        )
        self.assertEqual(
            sanitize_git_remote("git@github.com:owner/repo.git?token=x#fragment"),
            "github.com:owner/repo.git",
        )


if __name__ == "__main__":
    unittest.main()
