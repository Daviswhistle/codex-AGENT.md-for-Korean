from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import install_codex  # noqa: E402


@unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
class InstallerTests(unittest.TestCase):
    def homes(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp)
        return root / ".codex", root / ".agents" / "skills"

    def test_install_is_idempotent_and_checkable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, skills_home = self.homes(tmp)
            first = install_codex.install(ROOT, codex_home, skills_home)
            second = install_codex.install(ROOT, codex_home, skills_home)

            self.assertTrue(first.created_links)
            self.assertFalse(second.created_links)
            self.assertEqual(
                (codex_home / "AGENTS.md").resolve(strict=True),
                (ROOT / "AGENTS.md").resolve(),
            )
            for name in install_codex.discover_skills(ROOT):
                self.assertEqual(
                    (skills_home / name).resolve(strict=True),
                    (ROOT / "skills" / name).resolve(),
                )
            self.assertEqual(install_codex.check(ROOT, codex_home, skills_home), [])

    def test_conflict_fails_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, skills_home = self.homes(tmp)
            codex_home.mkdir(parents=True)
            (codex_home / "AGENTS.md").write_text("keep\n", encoding="utf-8")

            with self.assertRaises(install_codex.InstallError):
                install_codex.install(ROOT, codex_home, skills_home)

            self.assertFalse(skills_home.exists())
            self.assertEqual((codex_home / "AGENTS.md").read_text(), "keep\n")

    def test_legacy_skill_blocks_migration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, skills_home = self.homes(tmp)
            legacy = codex_home / "skills" / install_codex.discover_skills(ROOT)[0]
            legacy.mkdir(parents=True)

            with self.assertRaises(install_codex.InstallError) as raised:
                install_codex.install(ROOT, codex_home, skills_home)

            self.assertIn("legacy $CODEX_HOME/skills", str(raised.exception))
            self.assertFalse(skills_home.exists())

    def test_retired_skill_blocks_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, skills_home = self.homes(tmp)
            retired = skills_home / install_codex.RETIRED_SKILLS[-1]
            retired.mkdir(parents=True)

            with self.assertRaises(install_codex.InstallError):
                install_codex.install(ROOT, codex_home, skills_home)

    def test_partial_link_failure_rolls_back_created_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home, skills_home = self.homes(tmp)
            original = Path.symlink_to
            calls = 0

            def fail_second(path: Path, target: Path, target_is_directory: bool = False) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise PermissionError("simulated")
                original(path, target, target_is_directory=target_is_directory)

            with mock.patch.object(Path, "symlink_to", new=fail_second):
                with self.assertRaises(PermissionError):
                    install_codex.install(ROOT, codex_home, skills_home)

            self.assertFalse((codex_home / "AGENTS.md").exists())
            self.assertFalse(any(skills_home.iterdir()) if skills_home.exists() else False)


if __name__ == "__main__":
    unittest.main()
