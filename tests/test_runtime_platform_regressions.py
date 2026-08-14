from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from doctor import sanitize_git_remote  # noqa: E402


def copy_repo(destination: Path) -> Path:
    return shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
    )


def run_installer(
    repo_root: Path,
    codex_home: Path,
    *,
    root_argument: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [str(repo_root / "scripts" / "install_codex.sh")]
    if root_argument is not None:
        command.extend(("--root", str(root_argument)))
    command.extend(("--codex-home", str(codex_home)))
    return subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class DoctorSanitizationRegressionTests(unittest.TestCase):
    def test_non_numeric_port_like_netloc_does_not_break_sanitization(self) -> None:
        self.assertEqual(
            sanitize_git_remote(
                "https://user:secret@example.com:bad/owner/repo.git"
            ),
            "https://example.com:bad/owner/repo.git",
        )


@unittest.skipUnless(
    sys.platform == "darwin",
    "case-insensitive path alias regression is macOS-specific",
)
class MacOSPathIdentityRegressionTests(unittest.TestCase):
    def test_case_aliases_use_filesystem_identity(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="davis-agent-kit-home-alias-",
            dir=Path.home(),
        ) as tmp:
            repo_root = copy_repo(Path(tmp) / "checkout")
            real_codex_home = repo_root / ".codex"
            aliased_codex_home = Path(
                str(real_codex_home).replace("/Users/", "/users/", 1)
            )
            if (
                aliased_codex_home == real_codex_home
                or not aliased_codex_home.parent.exists()
            ):
                self.skipTest("home filesystem does not provide the macOS case alias")

            completed = run_installer(repo_root, aliased_codex_home)

            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertIn("Codex home is inside the checkout", completed.stdout)
            self.assertFalse(real_codex_home.exists())
            self.assertTrue((repo_root / "kit.toml").is_file())

        with tempfile.TemporaryDirectory(
            prefix="davis-agent-kit-case-",
            dir=Path.home(),
        ) as tmp:
            codex_home = Path(tmp) / ".codex"
            repo_root = copy_repo(codex_home / "davis-agent-kit")
            subprocess.run(("git", "init", "-q", str(repo_root)), check=True)
            aliased_repo_root = Path(
                str(repo_root).replace("/Users/", "/users/", 1)
            )
            if aliased_repo_root == repo_root or not aliased_repo_root.exists():
                self.skipTest("home filesystem does not provide the macOS case alias")

            first = run_installer(
                repo_root,
                codex_home,
                root_argument=aliased_repo_root,
            )
            second = run_installer(
                repo_root,
                codex_home,
                root_argument=aliased_repo_root,
            )

            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertEqual(second.returncode, 0, second.stdout)
            self.assertIn(f"KEEP {repo_root.resolve()} (checkout)", first.stdout)
            self.assertNotIn("LINK ", second.stdout)
            self.assertTrue(repo_root.is_dir())
            self.assertFalse(repo_root.is_symlink())
            self.assertTrue((repo_root / "kit.toml").is_file())


if __name__ == "__main__":
    unittest.main()
