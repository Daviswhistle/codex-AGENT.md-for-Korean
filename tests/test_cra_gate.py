from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "cra_gate.py"
SPEC = importlib.util.spec_from_file_location("cra_gate", MODULE_PATH)
assert SPEC and SPEC.loader
cra_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cra_gate)


def run(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def clean_review() -> dict[str, object]:
    return {
        "findings": [],
        "overall_correctness": "patch is correct",
        "overall_explanation": "No substantive findings.",
        "overall_confidence_score": 0.99,
    }


def findings_review() -> dict[str, object]:
    return {
        "findings": [
            {
                "title": "[P1] Preserve the configured timeout",
                "body": "The new path ignores the configured timeout.",
                "confidence_score": 0.97,
                "code_location": {
                    "absolute_file_path": "/tmp/example.py",
                    "line_range": {"start": 10, "end": 11},
                },
            }
        ],
        "overall_correctness": "patch is incorrect",
        "overall_explanation": "One substantive regression remains.",
        "overall_confidence_score": 0.96,
    }


class CraGateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.codex_home = self.root / "codex"
        self.repo.mkdir()
        run("git", "init", cwd=self.repo)
        run("git", "config", "user.email", "test@example.com", cwd=self.repo)
        run("git", "config", "user.name", "Test User", cwd=self.repo)
        (self.repo / "example.py").write_text("value = 1\n", encoding="utf-8")
        run("git", "add", "example.py", cwd=self.repo)
        run("git", "commit", "-m", "initial task", cwd=self.repo)
        self.env = mock.patch.dict(
            os.environ,
            {
                "CODEX_HOME": str(self.codex_home),
                "CODEX_THREAD_ID": "thread-test",
                "CODEX_SESSION_ID": "session-test",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temporary.cleanup()

    def arm(self, *, confirmed: bool = False) -> None:
        if confirmed:
            cra_gate._record_heartbeat(
                {"cwd": str(self.repo), "thread_id": "thread-test"},
                self.codex_home,
            )
        args = argparse.Namespace(
            repo=str(self.repo),
            commit="HEAD",
            entry_source="explicit-request",
            risk=None,
            allow_unconfirmed_hook=not confirmed,
            codex_home=str(self.codex_home),
        )
        self.assertEqual(cra_gate._arm(args), 0)

    def state(self) -> dict[str, object]:
        located = cra_gate._find_state(
            cra_gate._state_root(self.codex_home),
            self.repo.resolve(),
        )
        self.assertIsNotNone(located)
        assert located is not None
        return located[1]

    def stop(self) -> dict[str, object]:
        return cra_gate._handle_stop(
            {"cwd": str(self.repo), "stop_hook_active": True},
            self.codex_home,
        )

    def test_arm_requires_a_real_hook_heartbeat_by_default(self) -> None:
        args = argparse.Namespace(
            repo=str(self.repo),
            commit="HEAD",
            entry_source="explicit-request",
            risk=None,
            allow_unconfirmed_hook=False,
            codex_home=str(self.codex_home),
        )
        with self.assertRaises(cra_gate.CraError):
            cra_gate._arm(args)

        cra_gate._record_heartbeat({"cwd": str(self.repo)}, self.codex_home)
        self.assertEqual(cra_gate._arm(args), 0)
        self.assertEqual(self.state()["status"], "armed")

    def test_clean_review_allows_stop_and_records_terminal_state(self) -> None:
        self.arm()
        with mock.patch.object(cra_gate, "_run_review", return_value=clean_review()) as review:
            self.assertEqual(self.stop(), {})
        review.assert_called_once()
        state = self.state()
        self.assertEqual(state["status"], "completed-clean")
        self.assertEqual(state["reviewed_sha"], run("git", "rev-parse", "HEAD", cwd=self.repo))

    def test_findings_block_same_sha_without_re_review_then_review_amend(self) -> None:
        self.arm()
        with mock.patch.object(cra_gate, "_run_review", return_value=findings_review()) as review:
            result = self.stop()
            self.assertEqual(result["decision"], "block")
            self.assertIn("Preserve the configured timeout", result["reason"])
            duplicate = self.stop()
            self.assertEqual(duplicate["decision"], "block")
            self.assertEqual(review.call_count, 1)

        (self.repo / "example.py").write_text("value = 2\n", encoding="utf-8")
        run("git", "add", "example.py", cwd=self.repo)
        run("git", "commit", "--amend", "--no-edit", cwd=self.repo)

        with mock.patch.object(cra_gate, "_run_review", return_value=clean_review()) as review:
            self.assertEqual(self.stop(), {})
            review.assert_called_once()
        self.assertEqual(self.state()["status"], "completed-clean")

    def test_dirty_worktree_blocks_before_review(self) -> None:
        self.arm()
        (self.repo / "example.py").write_text("value = 3\n", encoding="utf-8")
        with mock.patch.object(cra_gate, "_run_review") as review:
            result = self.stop()
        self.assertEqual(result["decision"], "block")
        self.assertIn("worktree is not clean", result["reason"])
        review.assert_not_called()

    def test_second_commit_cannot_escape_the_armed_boundary(self) -> None:
        self.arm()
        (self.repo / "second.py").write_text("second = True\n", encoding="utf-8")
        run("git", "add", "second.py", cwd=self.repo)
        run("git", "commit", "-m", "unrelated second commit", cwd=self.repo)
        result = self.stop()
        self.assertEqual(result["decision"], "block")
        self.assertIn("before the first review", result["reason"])

    def test_review_failure_blocks_once_then_fails_open(self) -> None:
        self.arm()
        failure = cra_gate.CraError("quota unavailable")
        with mock.patch.object(cra_gate, "_run_review", side_effect=[failure, failure]) as review:
            first = self.stop()
            self.assertEqual(first["decision"], "block")
            self.assertIn("attempt 1/2", first["reason"])
            self.assertEqual(self.stop(), {})
            self.assertEqual(review.call_count, 2)
            self.assertEqual(self.stop(), {})
            self.assertEqual(review.call_count, 2)
        self.assertEqual(self.state()["status"], "failed-open")

    def test_reviewer_guard_prevents_recursive_review(self) -> None:
        self.arm()
        with mock.patch.dict(os.environ, {cra_gate.REVIEWER_GUARD: "1"}, clear=False):
            with mock.patch.object(cra_gate, "_run_review") as review:
                self.assertEqual(self.stop(), {})
        review.assert_not_called()
        self.assertEqual(self.state()["status"], "armed")

    def test_evidence_backed_rebuttal_allows_stop(self) -> None:
        self.arm()
        with mock.patch.object(cra_gate, "_run_review", return_value=findings_review()):
            self.assertEqual(self.stop()["decision"], "block")
        args = argparse.Namespace(
            repo=str(self.repo),
            commit="HEAD",
            reason="The configuration is read by the caller and covered by test_timeout.",
            codex_home=str(self.codex_home),
        )
        self.assertEqual(cra_gate._rebut(args), 0)
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.state()["status"], "completed-rebutted")

    def test_parse_review_accepts_fenced_json_and_rejects_malformed_output(self) -> None:
        fenced = "```json\n" + json.dumps(clean_review()) + "\n```"
        self.assertEqual(cra_gate._parse_review(fenced)["findings"], [])
        with self.assertRaises(cra_gate.CraError):
            cra_gate._parse_review("review passed")


class HookInstallationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.codex_home = self.root / "codex"
        self.args = argparse.Namespace(codex_home=str(self.codex_home))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def document(self) -> dict[str, object]:
        return json.loads((self.codex_home / "hooks.json").read_text(encoding="utf-8"))

    def managed_count(self, event: str) -> int:
        hooks = self.document()["hooks"][event]
        return sum(
            cra_gate._is_managed_handler(handler)
            for group in hooks
            for handler in group.get("hooks", [])
        )

    def test_install_preserves_existing_hooks_and_is_idempotent(self) -> None:
        self.codex_home.mkdir(parents=True)
        existing = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": "existing",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo existing",
                                "timeout": 10,
                            }
                        ],
                    }
                ]
            },
            "unrelated": {"preserve": True},
        }
        (self.codex_home / "hooks.json").write_text(json.dumps(existing), encoding="utf-8")

        self.assertEqual(cra_gate._install_hook(self.args), 0)
        self.assertEqual(cra_gate._install_hook(self.args), 0)
        document = self.document()
        self.assertEqual(document["unrelated"], {"preserve": True})
        self.assertEqual(self.managed_count("SessionStart"), 1)
        self.assertEqual(self.managed_count("Stop"), 1)
        stop_commands = [
            handler["command"]
            for group in document["hooks"]["Stop"]
            for handler in group.get("hooks", [])
        ]
        self.assertIn("echo existing", stop_commands)

    def test_uninstall_removes_only_managed_handlers(self) -> None:
        self.assertEqual(cra_gate._install_hook(self.args), 0)
        document = self.document()
        document["hooks"]["Stop"].append(
            {"hooks": [{"type": "command", "command": "echo keep"}]}
        )
        (self.codex_home / "hooks.json").write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(cra_gate._uninstall_hook(self.args), 0)
        document = self.document()
        commands = [
            handler["command"]
            for group in document["hooks"]["Stop"]
            for handler in group.get("hooks", [])
        ]
        self.assertEqual(commands, ["echo keep"])
        self.assertNotIn("SessionStart", document["hooks"])

    def test_invalid_hooks_file_is_never_overwritten(self) -> None:
        self.codex_home.mkdir(parents=True)
        path = self.codex_home / "hooks.json"
        path.write_text("{invalid", encoding="utf-8")
        with self.assertRaises(cra_gate.CraError):
            cra_gate._install_hook(self.args)
        self.assertEqual(path.read_text(encoding="utf-8"), "{invalid")


if __name__ == "__main__":
    unittest.main()
