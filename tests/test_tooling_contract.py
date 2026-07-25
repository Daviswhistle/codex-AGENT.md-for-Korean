from __future__ import annotations

from datetime import date
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import install_codex  # noqa: E402
from install_codex import install  # noqa: E402
from kit_manifest import ManifestError, load_manifest, validate_manifest  # noqa: E402
from validate_kit import discover_helper_smoke_checks, discover_test_suites  # noqa: E402


class ToolingContractTests(unittest.TestCase):
    def test_manifest_covers_every_installed_skill(self) -> None:
        manifest = load_manifest(ROOT)

        self.assertEqual(manifest.schema_version, 1)
        self.assertRegex(manifest.kit_version, r"^\d+\.\d+\.\d+")
        self.assertEqual(manifest.minimum_python, (3, 11))
        self.assertEqual(validate_manifest(manifest, ROOT), [])
        self.assertEqual(
            {skill.name for skill in manifest.skills},
            {
                "translation-quality",
                "handoff-agent-builder",
                "software-engineering",
                "writing-quality",
            },
        )
        self.assertEqual(
            set(manifest.install.retired_skills),
            {"davis-operating-system", "coding-workflow"},
        )

    def test_manifest_reports_broken_skill_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# Test\n", encoding="utf-8")

            listed = root / "skills" / "listed"
            listed.mkdir(parents=True)
            (listed / "SKILL.md").write_text(
                "---\n"
                "name: listed\n"
                "---\n"
                "# Listed\n\n"
                "Read `references/missing.md` and `references/../escape.md`.\n",
                encoding="utf-8",
            )

            unlisted = root / "skills" / "unlisted"
            unlisted.mkdir(parents=True)
            (unlisted / "SKILL.md").write_text(
                "---\nname: unlisted\ndescription: Unlisted test skill.\n---\n",
                encoding="utf-8",
            )

            (root / "kit.toml").write_text(
                'schema_version = 1\n'
                'kit_version = "0.1.0"\n'
                'minimum_python = "3.11"\n'
                'normative_source = "AGENTS.md"\n\n'
                '[install]\n'
                'kit_link = "nested/davis-agent-kit"\n'
                'agents_link = "AGENTS.md"\n'
                'skills_dir = "nested"\n'
                'retired_skills = ["listed"]\n\n'
                '[[skills]]\n'
                'name = "listed"\n'
                'path = "skills/listed"\n'
                'entrypoint = "SKILL.md"\n',
                encoding="utf-8",
            )

            errors = validate_manifest(load_manifest(root), root)

        joined = "\n".join(errors)
        self.assertIn("active skills also listed as retired: listed", joined)
        self.assertIn("skill description is missing or empty", joined)
        self.assertIn("missing resource referenced", joined)
        self.assertIn("unsafe resource referenced", joined)
        self.assertIn("skills missing from manifest: skills/unlisted", joined)
        self.assertIn("managed install paths overlap", joined)
        self.assertIn("install.kit_link must be a single path component", joined)

    def test_validate_kit_discovers_all_test_directories_and_helpers(self) -> None:
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

    def test_ci_runs_the_single_validation_entrypoint(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn('python-version: "3.11"', workflow)
        self.assertIn("python3 scripts/validate_kit.py", workflow)
        self.assertTrue((ROOT / "scripts" / "doctor.py").is_file())
        self.assertTrue((ROOT / "scripts" / "validate_kit.py").is_file())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_is_manifest_driven_and_idempotent(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            skills_home = codex_home / manifest.install.skills_dir

            command = (
                str(ROOT / "scripts" / "install_codex.sh"),
                "--codex-home",
                str(codex_home),
            )
            first = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            second = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertEqual(second.returncode, 0, second.stdout)
            self.assertNotIn("LINK ", second.stdout)

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
                    (skills_home / skill.name).resolve(strict=True),
                    skill.root(ROOT).resolve(),
                )
            for retired_name in manifest.install.retired_skills:
                retired = skills_home / retired_name
                self.assertFalse(retired.exists() or retired.is_symlink())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_refuses_existing_conflicts_without_changes(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            skills_home = codex_home / manifest.install.skills_dir
            skills_home.mkdir(parents=True)
            agents_path = codex_home / manifest.install.agents_link
            agents_path.write_text("existing instructions\n", encoding="utf-8")
            retired_path = skills_home / manifest.install.retired_skills[0]
            retired_path.mkdir()
            (retired_path / "sentinel.txt").write_text("keep me\n", encoding="utf-8")

            completed = subprocess.run(
                (
                    str(ROOT / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn("already exists and is not the expected link", completed.stdout)
            self.assertEqual(
                agents_path.read_text(encoding="utf-8"),
                "existing instructions\n",
            )
            self.assertEqual(
                (retired_path / "sentinel.txt").read_text(encoding="utf-8"),
                "keep me\n",
            )
            self.assertFalse(
                (codex_home / manifest.install.kit_link).exists()
            )

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_refuses_unlisted_kit_skill_without_changes(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            skills_home = codex_home / manifest.install.skills_dir
            skills_home.mkdir(parents=True)
            unlisted_path = skills_home / "old-kit-skill"
            unlisted_path.symlink_to(
                manifest.skills[0].root(ROOT),
                target_is_directory=True,
            )

            completed = subprocess.run(
                (
                    str(ROOT / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn(
                "Unlisted skill link points into this kit",
                completed.stdout,
            )
            self.assertTrue(unlisted_path.is_symlink())
            self.assertFalse(
                (codex_home / manifest.install.kit_link).exists()
            )
            self.assertFalse(
                (codex_home / manifest.install.agents_link).exists()
            )

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_refuses_unlisted_future_kit_alias(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            skills_home = codex_home / manifest.install.skills_dir
            skills_home.mkdir(parents=True)
            unlisted_path = skills_home / "old-kit-skill"
            unlisted_path.symlink_to(
                Path("..")
                / manifest.install.kit_link
                / manifest.skills[0].path,
                target_is_directory=True,
            )

            completed = subprocess.run(
                (
                    str(ROOT / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn(
                "Unlisted skill link points into this kit",
                completed.stdout,
            )
            self.assertTrue(unlisted_path.is_symlink())
            self.assertFalse(
                (codex_home / manifest.install.kit_link).exists()
            )

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_rolls_back_partial_mutation_failure(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            skills_home = codex_home / manifest.install.skills_dir
            skills_home.mkdir(parents=True)
            failing_path = skills_home / manifest.skills[0].name
            original_symlink_to = Path.symlink_to

            def fail_one_link(
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

            with mock.patch.object(Path, "symlink_to", new=fail_one_link):
                with self.assertRaises(ManifestError) as raised:
                    install(ROOT, codex_home)

            error = str(raised.exception)
            self.assertIn("simulated link failure", error)
            self.assertIn("Created installation paths were rolled back", error)
            self.assertFalse(
                (codex_home / manifest.install.kit_link).exists()
            )
            self.assertFalse(
                (codex_home / manifest.install.agents_link).exists()
            )
            self.assertFalse(failing_path.exists() or failing_path.is_symlink())
            self.assertFalse((codex_home / "backups").exists())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_rolls_back_when_stdout_closes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            process = subprocess.Popen(
                (
                    str(ROOT / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertIsNotNone(process.stdout)
            process.stdout.close()
            stderr = process.stderr.read() if process.stderr is not None else ""
            if process.stderr is not None:
                process.stderr.close()
            returncode = process.wait()

            self.assertNotEqual(returncode, 0)
            self.assertNotIn("Traceback", stderr)
            self.assertFalse(codex_home.exists())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_rolls_back_when_doctor_is_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    sys,
                    "argv",
                    ["install_codex.py", "--codex-home", str(codex_home)],
                ),
                mock.patch.object(install_codex, "run_doctor", side_effect=KeyboardInterrupt),
                mock.patch.object(sys, "stdout", stdout),
                mock.patch.object(sys, "stderr", stderr),
            ):
                returncode = install_codex.main()

            self.assertEqual(returncode, 130)
            self.assertIn("Created installation paths were rolled back", stderr.getvalue())
            self.assertFalse(codex_home.exists())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_ignores_final_success_write_failure(self) -> None:
        class BrokenOnSuccess(io.StringIO):
            def write(self, text: str) -> int:
                if "Codex installation is ready" in text:
                    raise BrokenPipeError("simulated final output failure")
                return super().write(text)

        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            stdout = BrokenOnSuccess()
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    sys,
                    "argv",
                    ["install_codex.py", "--codex-home", str(codex_home)],
                ),
                mock.patch.object(install_codex, "run_doctor", return_value=0),
                mock.patch.object(sys, "stdout", stdout),
                mock.patch.object(sys, "stderr", stderr),
            ):
                returncode = install_codex.main()

            self.assertEqual(returncode, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(
                (codex_home / manifest.install.kit_link).resolve(strict=True),
                ROOT.resolve(),
            )

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_refuses_managed_symlink_loop(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            skills_home = codex_home / manifest.install.skills_dir
            skills_home.mkdir(parents=True)
            (codex_home / manifest.install.kit_link).symlink_to(
                ROOT,
                target_is_directory=True,
            )
            agents_path = codex_home / manifest.install.agents_link
            agents_path.symlink_to(agents_path)

            completed = subprocess.run(
                (
                    str(ROOT / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertNotIn("Traceback", completed.stdout)
            self.assertIn(
                "already exists and is not the expected link",
                completed.stdout,
            )
            self.assertTrue(agents_path.is_symlink())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_preserves_checkout_at_kit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            repo_root = codex_home / "davis-agent-kit"
            shutil.copytree(
                ROOT,
                repo_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            manifest = load_manifest(repo_root)

            completed = subprocess.run(
                (
                    str(repo_root / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertIn(f"KEEP {repo_root.resolve()} (checkout)", completed.stdout)
            self.assertNotIn("BACKUP ", completed.stdout)
            self.assertTrue(repo_root.is_dir())
            self.assertFalse(repo_root.is_symlink())
            self.assertTrue((repo_root / "kit.toml").is_file())
            self.assertEqual(
                (codex_home / manifest.install.agents_link).resolve(strict=True),
                (repo_root / manifest.normative_source).resolve(),
            )
            for skill in manifest.skills:
                self.assertEqual(
                    (
                        codex_home
                        / manifest.install.skills_dir
                        / skill.name
                    ).resolve(strict=True),
                    skill.root(repo_root).resolve(),
                )

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_rejects_skills_root_symlink_into_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo_root = temp_root / "checkout"
            codex_home = temp_root / ".codex"
            shutil.copytree(
                ROOT,
                repo_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            codex_home.mkdir()
            skills_home = codex_home / "skills"
            skills_home.symlink_to(repo_root / "skills", target_is_directory=True)
            manifest = load_manifest(repo_root)

            completed = subprocess.run(
                (
                    str(repo_root / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn(
                "Codex skills root is a whole-directory symlink",
                completed.stdout,
            )
            self.assertIn(
                "no installation paths were changed",
                completed.stdout,
            )
            self.assertTrue(skills_home.is_symlink())
            self.assertEqual(
                skills_home.resolve(strict=True),
                (repo_root / "skills").resolve(),
            )
            self.assertFalse((codex_home / "AGENTS.md").exists())
            self.assertFalse((codex_home / "backups").exists())
            for skill in manifest.skills:
                source = skill.root(repo_root)
                self.assertTrue(source.is_dir())
                self.assertFalse(source.is_symlink())
                self.assertTrue(skill.entrypoint_path(repo_root).is_file())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_rejects_skills_link_before_repointing_kit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            new_repo = temp_root / "new-checkout"
            old_repo = temp_root / "old-checkout"
            codex_home = temp_root / ".codex"
            ignore = shutil.ignore_patterns(".git", "__pycache__", "*.pyc")
            shutil.copytree(ROOT, new_repo, ignore=ignore)
            shutil.copytree(ROOT, old_repo, ignore=ignore)
            codex_home.mkdir()
            kit_link = codex_home / "davis-agent-kit"
            kit_link.symlink_to(old_repo, target_is_directory=True)
            skills_home = codex_home / "skills"
            skills_home.symlink_to(
                kit_link / "skills",
                target_is_directory=True,
            )

            completed = subprocess.run(
                (
                    str(new_repo / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=new_repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn(
                "Codex skills root is a whole-directory symlink",
                completed.stdout,
            )
            self.assertIn(
                "no installation paths were changed",
                completed.stdout,
            )
            self.assertEqual(kit_link.resolve(strict=True), old_repo.resolve())
            self.assertEqual(
                skills_home.resolve(strict=True),
                (old_repo / "skills").resolve(),
            )
            self.assertFalse((codex_home / "AGENTS.md").exists())
            self.assertFalse((codex_home / "backups").exists())
            for source_repo in (new_repo, old_repo):
                manifest = load_manifest(source_repo)
                for skill in manifest.skills:
                    source = skill.root(source_repo)
                    self.assertTrue(source.is_dir())
                    self.assertFalse(source.is_symlink())
                    self.assertTrue(skill.entrypoint_path(source_repo).is_file())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_codex_installer_rejects_checkout_nested_under_kit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            kit_path = codex_home / "davis-agent-kit"
            repo_root = kit_path / "checkout"
            shutil.copytree(
                ROOT,
                repo_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )

            completed = subprocess.run(
                (
                    str(repo_root / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn(
                "checkout is nested under Codex home",
                completed.stdout,
            )
            self.assertIn(
                "no installation paths were changed",
                completed.stdout,
            )
            self.assertTrue(repo_root.is_dir())
            self.assertFalse(repo_root.is_symlink())
            self.assertTrue((repo_root / "kit.toml").is_file())
            self.assertFalse((codex_home / "AGENTS.md").exists())
            self.assertFalse((codex_home / "skills").exists())
            self.assertFalse((codex_home / "backups").exists())

    @unittest.skipUnless(
        sys.platform == "darwin",
        "case-insensitive path alias regression is macOS-specific",
    )
    def test_codex_installer_rejects_aliased_codex_home_inside_checkout(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="davis-agent-kit-home-alias-", dir=Path.home()
        ) as tmp:
            repo_root = Path(tmp) / "checkout"
            shutil.copytree(
                ROOT,
                repo_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            aliased_codex_home = Path(
                str(repo_root / ".codex").replace("/Users/", "/users/", 1)
            )
            if not aliased_codex_home.parent.exists():
                self.skipTest("home filesystem does not provide the macOS case alias")

            completed = subprocess.run(
                (
                    str(repo_root / "scripts" / "install_codex.sh"),
                    "--codex-home",
                    str(aliased_codex_home),
                ),
                cwd=repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn("Codex home is inside the checkout", completed.stdout)
            self.assertIn(
                "no installation paths were changed",
                completed.stdout,
            )
            self.assertFalse((repo_root / ".codex").exists())
            self.assertTrue((repo_root / "kit.toml").is_file())

    @unittest.skipUnless(
        sys.platform == "darwin",
        "case-insensitive path alias regression is macOS-specific",
    )
    def test_codex_installer_detects_direct_checkout_by_identity(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="davis-agent-kit-case-", dir=Path.home()
        ) as tmp:
            codex_home = Path(tmp) / ".codex"
            repo_root = codex_home / "davis-agent-kit"
            shutil.copytree(
                ROOT,
                repo_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            subprocess.run(
                ("git", "init", "-q", str(repo_root)),
                check=True,
            )
            aliased_repo_root = Path(
                str(repo_root).replace("/Users/", "/users/", 1)
            )
            if not aliased_repo_root.exists():
                self.skipTest("home filesystem does not provide the macOS case alias")

            completed = subprocess.run(
                (
                    str(repo_root / "scripts" / "install_codex.sh"),
                    "--root",
                    str(aliased_repo_root),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            repeated = subprocess.run(
                (
                    str(repo_root / "scripts" / "install_codex.sh"),
                    "--root",
                    str(aliased_repo_root),
                    "--codex-home",
                    str(codex_home),
                ),
                cwd=repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(repeated.returncode, 0, repeated.stdout)
            self.assertIn(f"KEEP {repo_root.resolve()} (checkout)", completed.stdout)
            self.assertNotIn("BACKUP ", completed.stdout)
            self.assertNotIn("BACKUP ", repeated.stdout)
            self.assertTrue(repo_root.is_dir())
            self.assertFalse(repo_root.is_symlink())
            self.assertTrue((repo_root / "kit.toml").is_file())
            self.assertFalse((codex_home / "backups").exists())

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_doctor_accepts_exact_codex_install_links(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            skills_home = codex_home / manifest.install.skills_dir
            skills_home.mkdir(parents=True)

            (codex_home / manifest.install.kit_link).symlink_to(
                ROOT, target_is_directory=True
            )
            (codex_home / manifest.install.agents_link).symlink_to(
                ROOT / manifest.normative_source
            )
            for skill in manifest.skills:
                (skills_home / skill.name).symlink_to(
                    skill.root(ROOT), target_is_directory=True
                )

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
        for skill in manifest.skills:
            self.assertEqual(by_code[f"skill-link:{skill.name}"]["level"], "PASS")
            self.assertEqual(
                by_code[f"skill-entrypoint:{skill.name}"]["level"], "PASS"
            )
        for retired_name in manifest.install.retired_skills:
            self.assertEqual(by_code[f"retired-skill:{retired_name}"]["level"], "PASS")

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_doctor_rejects_retired_kit_skill(self) -> None:
        manifest = load_manifest(ROOT)
        retired_name = manifest.install.retired_skills[0]
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            skills_home = codex_home / manifest.install.skills_dir
            skills_home.mkdir(parents=True)

            (codex_home / manifest.install.kit_link).symlink_to(
                ROOT, target_is_directory=True
            )
            (codex_home / manifest.install.agents_link).symlink_to(
                ROOT / manifest.normative_source
            )
            for skill in manifest.skills:
                (skills_home / skill.name).symlink_to(
                    skill.root(ROOT), target_is_directory=True
                )
            (skills_home / retired_name).symlink_to(
                ROOT / "skills" / retired_name, target_is_directory=True
            )

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

        self.assertEqual(completed.returncode, 1, completed.stdout)
        payload = json.loads(completed.stdout)
        by_code = {result["code"]: result for result in payload["results"]}
        self.assertEqual(by_code[f"retired-skill:{retired_name}"]["level"], "FAIL")


class UserModelContractTests(unittest.TestCase):
    REQUIRED_FIELDS = (
        "ID:",
        "상태:",
        "마지막 확인:",
        "재검토:",
        "관찰:",
        "근거:",
        "작업에 미치는 영향:",
        "승격:",
        "대체:",
        "확신도:",
    )
    ALLOWED_STATUSES = {
        "candidate",
        "confirmed",
        "promoted",
        "superseded",
        "retired",
    }

    def test_every_observation_has_lifecycle_fields_and_live_promotions(self) -> None:
        text = (ROOT / "user-model" / "observations.md").read_text(encoding="utf-8")
        entries = re.split(r"(?m)^### ", text)[1:]
        self.assertGreater(len(entries), 0)

        ids: set[str] = set()
        records: dict[str, tuple[str, str, str]] = {}
        for entry in entries:
            title = entry.splitlines()[0]
            for field in self.REQUIRED_FIELDS:
                self.assertIn(field, entry, f"{title}: missing {field}")

            id_match = re.search(r"(?m)^ID: (OBS-\d{4}-\d{2}-\d{2}-\d{3})$", entry)
            self.assertIsNotNone(id_match, title)
            observation_id = id_match.group(1)
            self.assertNotIn(observation_id, ids)
            ids.add(observation_id)

            status_match = re.search(r"(?m)^상태: ([a-z]+)$", entry)
            self.assertIsNotNone(status_match, title)
            status = status_match.group(1)
            self.assertIn(status, self.ALLOWED_STATUSES)

            confirmed_match = re.search(r"(?m)^마지막 확인: (\d{4}-\d{2}-\d{2})$", entry)
            review_match = re.search(r"(?m)^재검토: (.+)$", entry)
            self.assertIsNotNone(confirmed_match, title)
            self.assertIsNotNone(review_match, title)
            confirmed_date = date.fromisoformat(confirmed_match.group(1))
            review_value = review_match.group(1).strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", review_value):
                self.assertGreaterEqual(date.fromisoformat(review_value), confirmed_date)
            else:
                self.assertRegex(review_value, r"^조건: \S.+", title)

            promotion_match = re.search(
                r"(?ms)^승격:\n(?P<body>.*?)\n\n대체:", entry
            )
            self.assertIsNotNone(promotion_match, title)
            promotion_paths = re.findall(r"`([^`]+)`", promotion_match.group("body"))
            if status == "promoted":
                self.assertGreater(len(promotion_paths), 0, title)
            for rel_path in promotion_paths:
                promotion_path = Path(rel_path)
                self.assertFalse(promotion_path.is_absolute(), title)
                self.assertNotIn("..", promotion_path.parts, title)
                self.assertTrue((ROOT / promotion_path).exists(), f"{title}: stale {rel_path}")

            replacement_match = re.search(
                r"(?ms)^대체:\n(?P<body>.*?)\n\n확신도:", entry
            )
            self.assertIsNotNone(replacement_match, title)
            replacement = replacement_match.group("body").strip()
            self.assertTrue(
                replacement == "없음"
                or re.fullmatch(
                    r"(?:supersedes|superseded_by) OBS-\d{4}-\d{2}-\d{2}-\d{3}",
                    replacement,
                ),
                f"{title}: invalid replacement relation {replacement!r}",
            )
            records[observation_id] = (status, replacement, title)

        for observation_id, (status, replacement, title) in records.items():
            if replacement == "없음":
                self.assertNotEqual(status, "superseded", title)
                continue

            relation, target_id = replacement.split(maxsplit=1)
            self.assertIn(target_id, records, f"{title}: unknown replacement target")
            self.assertNotEqual(target_id, observation_id, title)
            target_status, target_replacement, _ = records[target_id]

            if relation == "superseded_by":
                self.assertEqual(status, "superseded", title)
                self.assertEqual(
                    target_replacement,
                    f"supersedes {observation_id}",
                    f"{title}: replacement relation is not reciprocal",
                )
            else:
                self.assertEqual(target_status, "superseded", title)
                self.assertEqual(
                    target_replacement,
                    f"superseded_by {observation_id}",
                    f"{title}: replacement relation is not reciprocal",
                )


if __name__ == "__main__":
    unittest.main()
