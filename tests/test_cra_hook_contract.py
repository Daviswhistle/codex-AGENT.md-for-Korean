from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "scripts" / "cra_control.py"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cra_control import HOOK_TIMEOUT_SECONDS, REVIEW_TIMEOUT_SECONDS  # noqa: E402


class CraHookContractTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "managed kit link is POSIX-oriented")
    def test_hook_config_is_explicit_read_only_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            managed_kit = codex_home / "davis-agent-kit"
            managed_kit.symlink_to(ROOT, target_is_directory=True)
            env = dict(os.environ)
            env["CODEX_HOME"] = str(codex_home)

            completed = subprocess.run(
                (sys.executable, str(CONTROLLER), "hook-config"),
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            data = json.loads(completed.stdout)
            self.assertEqual(
                set(data["hooks"]),
                {"SessionStart", "UserPromptSubmit", "Stop"},
            )
            commands: set[str] = set()
            stop_timeout = None
            for event, matchers in data["hooks"].items():
                self.assertEqual(len(matchers), 1, event)
                hook = matchers[0]["hooks"][0]
                commands.add(hook["command"])
                if event == "Stop":
                    stop_timeout = hook["timeout"]

            expected_controller = managed_kit / "scripts" / "cra_control.py"
            self.assertEqual(
                commands,
                {f"python3 {expected_controller} hook"},
            )
            self.assertEqual(stop_timeout, HOOK_TIMEOUT_SECONDS)
            self.assertGreater(HOOK_TIMEOUT_SECONDS, REVIEW_TIMEOUT_SECONDS)
            self.assertFalse((codex_home / "hooks.json").exists())

    def test_hook_config_requires_the_managed_install_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            env = dict(os.environ)
            env["CODEX_HOME"] = str(codex_home)

            completed = subprocess.run(
                (sys.executable, str(CONTROLLER), "hook-config"),
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("run scripts/install_codex.sh first", completed.stderr)
            self.assertEqual(completed.stdout, "")

    def test_readme_requires_review_before_manual_hook_install(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("### CRA Stop hook 명시적 활성화", 1)[1].split(
            "### Hook-managed CRA", 1
        )[0]

        self.assertIn("hook-config", section)
        self.assertIn("cat \"$HOOK_DRAFT\"", section)
        self.assertIn("test ! -e \"$CODEX_DIR/hooks.json\"", section)
        self.assertIn("기존 hook이 있으면", section)
        self.assertIn("자동 덮어쓰기는 하지 않습니다", section)
        self.assertIn("`/hooks`", section)


if __name__ == "__main__":
    unittest.main()
