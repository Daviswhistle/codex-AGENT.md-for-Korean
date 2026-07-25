from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import install_codex  # noqa: E402


class InstallCodexReviewFeedbackTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_interrupt_during_link_creation_rolls_back_and_returns_130(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            parent = temp_root / "created-parent"
            codex_home = parent / "nested" / ".codex"
            original_symlink_to = Path.symlink_to
            call_count = 0

            def interrupt_third_link(
                path: Path,
                target: Path,
                target_is_directory: bool = False,
            ) -> None:
                nonlocal call_count
                call_count += 1
                original_symlink_to(
                    path,
                    target,
                    target_is_directory=target_is_directory,
                )
                if call_count == 3:
                    raise KeyboardInterrupt

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    sys,
                    "argv",
                    ["install_codex.py", "--codex-home", str(codex_home)],
                ),
                mock.patch.object(Path, "symlink_to", new=interrupt_third_link),
                mock.patch.object(install_codex, "run_doctor") as run_doctor,
                mock.patch.object(sys, "stdout", stdout),
                mock.patch.object(sys, "stderr", stderr),
            ):
                returncode = install_codex.main()

            self.assertEqual(returncode, 130)
            self.assertIn(
                "Created installation paths were rolled back",
                stderr.getvalue(),
            )
            self.assertFalse(parent.exists())
            run_doctor.assert_not_called()

    @unittest.skipIf(os.name == "nt", "symlink contract is POSIX-oriented")
    def test_doctor_failure_removes_every_created_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            parent = temp_root / "created-parent"
            codex_home = parent / "nested" / ".codex"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                mock.patch.object(
                    sys,
                    "argv",
                    ["install_codex.py", "--codex-home", str(codex_home)],
                ),
                mock.patch.object(install_codex, "run_doctor", return_value=7),
                mock.patch.object(sys, "stdout", stdout),
                mock.patch.object(sys, "stderr", stderr),
            ):
                returncode = install_codex.main()

            self.assertEqual(returncode, 7)
            self.assertIn(
                "Created installation paths were rolled back",
                stderr.getvalue(),
            )
            self.assertFalse(parent.exists())


if __name__ == "__main__":
    unittest.main()
