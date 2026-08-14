from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "scripts" / "cra_control.py"
SESSION_ID = "thr_test_root_session"


class CraControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.codex_home = self.root / "codex-home"
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.calls = self.root / "codex-call.json"

        subprocess.run(("git", "init", "-q", str(self.repo)), check=True)
        subprocess.run(
            ("git", "-C", str(self.repo), "config", "user.email", "test@example.com"),
            check=True,
        )
        subprocess.run(
            ("git", "-C", str(self.repo), "config", "user.name", "Test"),
            check=True,
        )
        (self.repo / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "tracked.txt"), check=True)
        subprocess.run(
            ("git", "-C", str(self.repo), "commit", "-qm", "initial"),
            check=True,
        )
        self.commit = subprocess.check_output(
            ("git", "-C", str(self.repo), "rev-parse", "HEAD"),
            text=True,
        ).strip()

        fake_codex = self.bin_dir / "codex"
        fake_codex.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "pathlib.Path(os.environ['FAKE_CODEX_CALLS']).write_text(\n"
            "    json.dumps({\n"
            "        'args': sys.argv[1:],\n"
            "        'child': os.environ.get('DAVIS_CRA_REVIEW_CHILD'),\n"
            "        'session': os.environ.get('CODEX_SESSION_ID'),\n"
            "        'thread': os.environ.get('CODEX_THREAD_ID'),\n"
            "    }), encoding='utf-8'\n"
            ")\n"
            "print('Codex Review: [P1] simulated substantive finding')\n",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)

        self.env = dict(os.environ)
        self.env.update(
            {
                "CODEX_HOME": str(self.codex_home),
                "CODEX_SESSION_ID": SESSION_ID,
                "CODEX_THREAD_ID": SESSION_ID,
                "FAKE_CODEX_CALLS": str(self.calls),
                "PATH": str(self.bin_dir) + os.pathsep + self.env.get("PATH", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )

    def run_control(
        self,
        *args: str,
        payload: dict[str, object] | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, str(CONTROLLER), *args),
            cwd=self.repo,
            env=self.env if env is None else env,
            input=json.dumps(payload) if payload is not None else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def hook_payload(self, event: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "session_id": SESSION_ID,
            "cwd": str(self.repo),
            "hook_event_name": event,
        }
        if event == "Stop":
            payload.update(
                {
                    "turn_id": "turn_test",
                    "stop_hook_active": False,
                    "last_assistant_message": "CRA prepared",
                }
            )
        return payload

    def activate(self, event: str = "SessionStart") -> None:
        completed = self.run_control("hook", payload=self.hook_payload(event))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "")

    def prepare(self, *, entry_source: str = "explicit-request", extra: tuple[str, ...] = ()):
        completed = self.run_control(
            "prepare",
            "--commit",
            self.commit,
            "--entry-source",
            entry_source,
            *extra,
        )
        return completed

    def state_path(self) -> Path:
        key = hashlib.sha256(SESSION_ID.encode("utf-8")).hexdigest()
        return self.codex_home / "davis-cra" / "sessions" / key / "state.json"

    def read_state(self) -> dict[str, object]:
        return json.loads(self.state_path().read_text(encoding="utf-8"))

    def test_stop_runs_exact_reviewer_once_and_returns_continuation(self) -> None:
        self.activate()
        prepared = self.prepare()
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(json.loads(prepared.stdout)["status"], "prepared")

        stopped = self.run_control("hook", payload=self.hook_payload("Stop"))
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        response = json.loads(stopped.stdout)
        self.assertEqual(response["decision"], "block")
        self.assertIn("state=completed-output", response["reason"])
        self.assertIn("simulated substantive finding", response["reason"])

        call = json.loads(self.calls.read_text(encoding="utf-8"))
        self.assertEqual(
            call["args"],
            [
                "review",
                "--commit",
                self.commit,
                "-c",
                'model="gpt-5.6-sol"',
                "-c",
                'model_reasoning_effort="max"',
            ],
        )
        self.assertEqual(call["child"], "1")
        self.assertIsNone(call["session"])
        self.assertIsNone(call["thread"])
        self.assertNotIn("service_tier", " ".join(call["args"]))

        state = self.read_state()
        self.assertIsNone(state["pending"])
        self.assertEqual(state["last_result"]["state"], "completed-output")

        second = self.run_control("hook", payload=self.hook_payload("Stop"))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, "")

    def test_user_prompt_submit_activates_current_session(self) -> None:
        self.activate("UserPromptSubmit")
        prepared = self.prepare()
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(json.loads(prepared.stdout)["mode"], "stop-hook")

    def test_prepare_requires_hook_activation(self) -> None:
        prepared = self.prepare()
        self.assertEqual(prepared.returncode, 3)
        self.assertEqual(json.loads(prepared.stdout)["status"], "fallback-required")
        self.assertIn("/hooks", prepared.stdout)

    def test_prepare_is_idempotent_for_same_boundary(self) -> None:
        self.activate()
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertFalse(json.loads(first.stdout)["idempotent"])
        self.assertTrue(json.loads(second.stdout)["idempotent"])
        self.assertEqual(
            json.loads(first.stdout)["attempt"],
            json.loads(second.stdout)["attempt"],
        )

    def test_stop_rejects_head_movement_without_running_reviewer(self) -> None:
        self.activate()
        self.assertEqual(self.prepare().returncode, 0)
        (self.repo / "tracked.txt").write_text("two\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "tracked.txt"), check=True)
        subprocess.run(
            ("git", "-C", str(self.repo), "commit", "-qm", "move head"),
            check=True,
        )

        stopped = self.run_control("hook", payload=self.hook_payload("Stop"))
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertIn("state=failed", json.loads(stopped.stdout)["reason"])
        self.assertIn("HEAD moved", json.loads(stopped.stdout)["reason"])
        self.assertFalse(self.calls.exists())

    def test_stop_rejects_worktree_drift_without_running_reviewer(self) -> None:
        self.activate()
        self.assertEqual(self.prepare().returncode, 0)
        (self.repo / "new.txt").write_text("drift\n", encoding="utf-8")

        stopped = self.run_control("hook", payload=self.hook_payload("Stop"))
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertIn("worktree or index changed", json.loads(stopped.stdout)["reason"])
        self.assertFalse(self.calls.exists())

    def test_reviewer_child_hook_is_noop_and_preserves_pending_state(self) -> None:
        self.activate()
        self.assertEqual(self.prepare().returncode, 0)
        child_env = dict(self.env)
        child_env["DAVIS_CRA_REVIEW_CHILD"] = "1"

        stopped = self.run_control(
            "hook", payload=self.hook_payload("Stop"), env=child_env
        )
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertEqual(stopped.stdout, "")
        self.assertIsNotNone(self.read_state()["pending"])
        self.assertFalse(self.calls.exists())

    def test_running_attempt_is_not_reexecuted(self) -> None:
        self.activate()
        self.assertEqual(self.prepare().returncode, 0)
        state = self.read_state()
        state["pending"]["phase"] = "running"
        self.state_path().write_text(json.dumps(state), encoding="utf-8")

        stopped = self.run_control("hook", payload=self.hook_payload("Stop"))
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        reason = json.loads(stopped.stdout)["reason"]
        self.assertIn("state=failed", reason)
        self.assertIn("automatic re-execution is disabled", reason)
        self.assertFalse(self.calls.exists())

    def test_autonomous_risk_requires_rationale(self) -> None:
        self.activate()
        prepared = self.prepare(entry_source="autonomous-risk")
        self.assertEqual(prepared.returncode, 1)
        self.assertIn("requires --risk-rationale", prepared.stderr)

    def test_managed_runtime_symlink_is_rejected(self) -> None:
        self.codex_home.mkdir()
        outside = self.root / "outside-runtime"
        outside.mkdir()
        (self.codex_home / "davis-cra").symlink_to(outside, target_is_directory=True)

        activated = self.run_control("hook", payload=self.hook_payload("SessionStart"))
        self.assertEqual(activated.returncode, 1)
        self.assertIn("must not be a symlink", activated.stderr)

    def test_existing_review_log_symlink_is_not_followed(self) -> None:
        self.activate()
        self.assertEqual(self.prepare().returncode, 0)
        state_path = self.state_path()
        log_path = state_path.parent / "review-0001.log"
        victim = self.root / "victim.txt"
        victim.write_text("keep\n", encoding="utf-8")
        log_path.symlink_to(victim)

        stopped = self.run_control("hook", payload=self.hook_payload("Stop"))
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertIn("state=failed", json.loads(stopped.stdout)["reason"])
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
