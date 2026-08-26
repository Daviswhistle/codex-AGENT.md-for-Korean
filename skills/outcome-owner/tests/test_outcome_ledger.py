from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "outcome_ledger.py"
LEDGER_MODULE = runpy.run_path(str(SCRIPT))
APPLICATION_ID = int(LEDGER_MODULE["APPLICATION_ID"])


class OutcomeLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.db = self.root / "private-state" / "objectives.sqlite3"

    def run_cli(
        self,
        *arguments: str,
        expect_success: bool = True,
        db_path: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = subprocess.run(
            self.cli_command(*arguments, db_path=db_path),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
        )
        if expect_success:
            self.assertEqual(
                completed.returncode,
                0,
                f"stdout={completed.stdout}\nstderr={completed.stderr}",
            )
            self.assertTrue(completed.stdout.strip())
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(completed.stderr, "")
        else:
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(completed.stdout, "")
            self.assertTrue(completed.stderr.strip())
            payload = json.loads(completed.stderr)
            self.assertFalse(payload["ok"])
        return completed, payload

    def cli_command(self, *arguments: str, db_path: Path | None = None) -> list[str]:
        return [
            sys.executable,
            str(SCRIPT),
            "--db",
            str(db_path or self.db),
            *arguments,
        ]

    def start(
        self,
        *,
        key: str = "start-1",
        objective: str = "Deliver the requested outcome",
        purpose: str = "Preserve the user's intended result and decision principles",
        constraints: tuple[str, ...] = (
            "Do not perform external writes",
            "Preserve unrelated repository changes",
        ),
        repo: Path | None = None,
        authority: str = "local-write",
        expect_success: bool = True,
    ) -> dict[str, object]:
        arguments = [
            "start",
            "--objective",
            objective,
            "--purpose",
            purpose,
            "--desired-state",
            "The result is verified and ready for the user",
            "--success-criterion",
            "Focused validation passes",
            "--success-criterion",
            "The diff matches the objective",
            "--repo-root",
            str(repo or self.repo),
            "--authority",
            authority,
            "--idempotency-key",
            key,
        ]
        for constraint in constraints:
            arguments.extend(["--constraint", constraint])
        _, payload = self.run_cli(*arguments, expect_success=expect_success)
        return payload

    def mission_id(self, **kwargs: object) -> str:
        payload = self.start(**kwargs)
        mission = payload["mission"]
        self.assertIsInstance(mission, dict)
        return str(mission["id"])

    def claim(
        self,
        mission_id: str,
        owner: str = "owner-a",
        ttl: str = "30",
        expected_generation: int | None = None,
        expected_version: int | None = None,
    ) -> dict[str, object]:
        if expected_generation is None or expected_version is None:
            with sqlite3.connect(self.db) as connection:
                observed = connection.execute(
                    "SELECT lease_generation, version FROM missions WHERE id = ?",
                    (mission_id,),
                ).fetchone()
            self.assertIsNotNone(observed)
            if expected_generation is None:
                expected_generation = observed[0]
            if expected_version is None:
                expected_version = observed[1]
        return self.run_cli(
            "claim",
            mission_id,
            "--owner",
            owner,
            "--expected-generation",
            str(expected_generation),
            "--expected-version",
            str(expected_version),
            "--ttl-seconds",
            ttl,
        )[1]

    def record(
        self,
        mission_id: str,
        *,
        owner: str = "owner-a",
        lease_generation: int | None = None,
        kind: str = "progress",
        summary: str = "Work advanced",
        key: str = "record-1",
        metadata: str = "{}",
        expect_success: bool = True,
    ) -> dict[str, object]:
        if lease_generation is None:
            lease_generation = self.latest_lease_generation(mission_id)
        return self.run_cli(
            "record",
            mission_id,
            "--owner",
            owner,
            "--lease-generation",
            str(lease_generation),
            "--kind",
            kind,
            "--summary",
            summary,
            "--metadata-json",
            metadata,
            "--idempotency-key",
            key,
            expect_success=expect_success,
        )[1]

    def transition(
        self,
        mission_id: str,
        to_state: str,
        *,
        owner: str = "owner-a",
        lease_generation: int | None = None,
        summary: str | None = None,
        key: str | None = None,
        expected_version: int = 1,
        completion_summary: str | None = None,
        expect_success: bool = True,
    ) -> dict[str, object]:
        if lease_generation is None:
            lease_generation = self.latest_lease_generation(mission_id)
        arguments = [
            "transition",
            mission_id,
            "--owner",
            owner,
            "--lease-generation",
            str(lease_generation),
            "--to",
            to_state,
            "--expected-version",
            str(expected_version),
            "--summary",
            summary or f"Transition to {to_state}",
            "--idempotency-key",
            key or f"transition-{to_state}",
        ]
        if completion_summary is not None:
            arguments.extend(["--completion-summary", completion_summary])
        return self.run_cli(*arguments, expect_success=expect_success)[1]

    def latest_lease_generation(self, mission_id: str) -> int:
        with sqlite3.connect(self.db) as connection:
            row = connection.execute(
                """
                SELECT COALESCE(
                    (SELECT generation FROM leases WHERE mission_id = missions.id),
                    lease_generation
                )
                FROM missions WHERE id = ?
                """,
                (mission_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        return int(row[0])

    def expire_lease(self, mission_id: str) -> None:
        with sqlite3.connect(self.db) as connection:
            row = connection.execute(
                "SELECT updated_at FROM missions WHERE id = ?",
                (mission_id,),
            ).fetchone()
            self.assertIsNotNone(row)
            expired_at = min(time.time() - 1.0, float(row[0]))
            connection.execute(
                """
                UPDATE leases
                SET acquired_at = ?, heartbeat_at = ?, expires_at = ?
                WHERE mission_id = ?
                """,
                (expired_at - 2.0, expired_at - 1.0, expired_at, mission_id),
            )
            connection.commit()

    def database_file_set(
        self,
        db_path: Path | None = None,
    ) -> dict[str, tuple[bytes, int]]:
        database = db_path or self.db
        snapshot: dict[str, tuple[bytes, int]] = {}
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = Path(str(database) + suffix)
            if os.path.lexists(path):
                snapshot[suffix] = (
                    path.read_bytes(),
                    stat.S_IMODE(path.stat().st_mode),
                )
        return snapshot

    def readonly_journal_mode(self, db_path: Path | None = None) -> str:
        database = (db_path or self.db).resolve()
        connection = sqlite3.connect(
            database.as_uri() + "?mode=ro&immutable=1&cache=private",
            uri=True,
        )
        try:
            return str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        finally:
            connection.close()

    def crash_wal_pragma(self, pragma: str) -> None:
        crash = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import os
import sqlite3
import sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute('PRAGMA wal_autocheckpoint = 0')
connection.execute('BEGIN IMMEDIATE')
connection.execute(sys.argv[2])
connection.commit()
os._exit(0)
""",
                str(self.db),
                pragma,
            ],
            check=False,
        )
        self.assertEqual(crash.returncode, 0)

    def test_start_is_idempotent_and_mismatch_fails_closed(self) -> None:
        first = self.start()
        second = self.start()

        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(first["mission"]["id"], second["mission"]["id"])
        self.assertEqual(first["mission"]["state"], "active")
        self.assertEqual(first["mission"]["version"], 1)
        self.assertEqual(
            first["mission"]["purpose"],
            "Preserve the user's intended result and decision principles",
        )
        self.assertEqual(
            first["mission"]["constraints"],
            ["Do not perform external writes", "Preserve unrelated repository changes"],
        )
        repo_stat = self.repo.stat()
        self.assertEqual(first["mission"]["repo_identity"]["device"], str(repo_stat.st_dev))
        self.assertEqual(first["mission"]["repo_identity"]["inode"], str(repo_stat.st_ino))
        self.assertEqual(
            set(first["mission"]["repo_identity"]["creation"]),
            {"kind", "value"},
        )
        self.assertTrue(first["mission"]["repo_identity"]["creation"]["kind"])
        self.assertTrue(first["mission"]["repo_identity"]["creation"]["value"])
        expected_case_sensitive = LEDGER_MODULE["filesystem_is_case_sensitive"](
            self.repo.resolve(),
            repo_stat,
        )
        self.assertEqual(
            first["mission"]["repo_path_case_sensitive"],
            expected_case_sensitive,
        )
        self.assertEqual(first["mission"]["lease_generation"], 0)

        _, conflict = self.run_cli(
            "start",
            "--objective",
            "A different objective",
            "--purpose",
            "Preserve the user's intended result and decision principles",
            "--desired-state",
            "The result is verified and ready for the user",
            "--success-criterion",
            "Focused validation passes",
            "--success-criterion",
            "The diff matches the objective",
            "--constraint",
            "Do not perform external writes",
            "--constraint",
            "Preserve unrelated repository changes",
            "--repo-root",
            str(self.repo),
            "--authority",
            "local-write",
            "--idempotency-key",
            "start-1",
            expect_success=False,
        )
        self.assertEqual(conflict["error"]["code"], "idempotency_conflict")

    def test_start_replay_recovers_contract_when_repo_is_missing(self) -> None:
        first = self.start()
        self.repo.rmdir()

        replay = self.start()
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["mission"]["id"], first["mission"]["id"])
        self.assertEqual(
            replay["mission"]["repo_identity"],
            first["mission"]["repo_identity"],
        )

        mismatch = self.start(
            objective="A changed objective",
            expect_success=False,
        )
        self.assertEqual(mismatch["error"]["code"], "idempotency_conflict")

        blank_purpose = self.start(
            key="blank-purpose",
            purpose=" ",
            expect_success=False,
        )
        self.assertEqual(blank_purpose["error"]["code"], "invalid_input")
        blank_constraint = self.start(
            key="blank-constraint",
            constraints=(" ",),
            expect_success=False,
        )
        self.assertEqual(blank_constraint["error"]["code"], "invalid_input")
        missing_constraint = self.start(
            key="missing-constraint",
            constraints=(),
            expect_success=False,
        )
        self.assertEqual(missing_constraint["error"]["code"], "invalid_arguments")

    def test_repo_root_must_resolve_to_existing_directory(self) -> None:
        missing = self.root / "missing"
        _, failure = self.run_cli(
            "start",
            "--objective",
            "Inspect a repository",
            "--purpose",
            "Base the decision on current repository evidence",
            "--desired-state",
            "Inspection complete",
            "--success-criterion",
            "Evidence recorded",
            "--constraint",
            "Do not modify the repository",
            "--repo-root",
            str(missing),
            "--authority",
            "read-only",
            "--idempotency-key",
            "missing-repo",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "invalid_repo_root")

        payload = self.start(key="valid-repo", authority="read-only")
        self.assertEqual(payload["mission"]["repo_root"], str(self.repo.resolve()))

    def test_empty_repo_root_is_rejected_instead_of_becoming_cwd(self) -> None:
        unused_db = self.root / "empty-root-state" / "objectives.sqlite3"
        completed, failure = self.run_cli(
            "start",
            "--objective",
            "Bind one explicit repository",
            "--purpose",
            "Keep the ownership scope unambiguous",
            "--desired-state",
            "No implicit working-directory binding",
            "--success-criterion",
            "Empty paths are rejected",
            "--constraint",
            "Do not create ledger state",
            "--repo-root",
            "",
            "--authority",
            "read-only",
            "--idempotency-key",
            "empty-repo-root",
            expect_success=False,
            db_path=unused_db,
        )
        self.assertEqual(failure["error"]["code"], "invalid_repo_root")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(unused_db.parent.exists())

        mission_id = self.mission_id(key="empty-list-root")
        source_before = self.database_file_set()
        completed, failure = self.run_cli(
            "list",
            "--repo-root",
            "",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "invalid_repo_root")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)
        self.assertEqual(self.run_cli("show", mission_id)[1]["mission"]["id"], mission_id)

    def test_start_rejects_database_inside_repo_before_creating_state(self) -> None:
        nested_db = self.repo / ".outcome-owner" / "objectives.sqlite3"
        completed, failure = self.run_cli(
            "start",
            "--objective",
            "Inspect a repository",
            "--purpose",
            "Preserve repository evidence",
            "--desired-state",
            "Inspection complete",
            "--success-criterion",
            "Evidence recorded",
            "--constraint",
            "Do not modify the repository",
            "--repo-root",
            str(self.repo),
            "--authority",
            "read-only",
            "--idempotency-key",
            "nested-database",
            expect_success=False,
            db_path=nested_db,
        )
        self.assertEqual(failure["error"]["code"], "invalid_db_path")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(nested_db.parent.exists())

    def test_existing_ledger_inside_governed_repo_is_rejected_without_mutation(
        self,
    ) -> None:
        self.mission_id(key="existing-overlap")
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0],
                "delete",
            )
        nested_dir = self.repo / ".outcome-owner"
        nested_dir.mkdir()
        nested_db = nested_dir / "objectives.sqlite3"
        for suffix in ("", "-journal", "-wal", "-shm"):
            source = Path(str(self.db) + suffix)
            if os.path.lexists(source):
                source.rename(Path(str(nested_db) + suffix))

        inspect_database = LEDGER_MODULE["inspect_recovered_database"]
        function_globals = inspect_database.__globals__
        original_inspect_clone = function_globals["inspect_recovered_clone"]
        observed_clone_paths: list[Path] = []

        def observe_clone(clone_path: Path) -> object:
            observed_clone_paths.append(clone_path)
            return original_inspect_clone(clone_path)

        function_globals["inspect_recovered_clone"] = observe_clone
        try:
            inspect_database(nested_db)
        finally:
            function_globals["inspect_recovered_clone"] = original_inspect_clone

        preflight_root = LEDGER_MODULE["preflight_workspace_root"]()
        self.assertTrue(observed_clone_paths)
        self.assertTrue(
            all(path.is_relative_to(preflight_root) for path in observed_clone_paths)
        )
        self.assertTrue(
            all(not path.is_relative_to(self.repo) for path in observed_clone_paths)
        )
        source_before = self.database_file_set(nested_db)

        completed, failure = self.run_cli(
            "list",
            expect_success=False,
            db_path=nested_db,
        )
        self.assertEqual(failure["error"]["code"], "invalid_db_path")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(nested_db), source_before)

    def test_huge_sqlite_limit_is_a_structured_argument_error(self) -> None:
        unused_db = self.root / "must-not-exist" / "objectives.sqlite3"
        completed, failure = self.run_cli(
            "list",
            "--limit",
            str(1 << 100),
            expect_success=False,
            db_path=unused_db,
        )
        self.assertEqual(failure["error"]["code"], "invalid_arguments")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(unused_db.exists())

    @unittest.skipUnless(os.name == "posix", "symlink loops require POSIX semantics")
    def test_looping_repo_and_database_paths_fail_with_structured_json(self) -> None:
        repo_loop_a = self.root / "repo-loop-a"
        repo_loop_b = self.root / "repo-loop-b"
        repo_loop_a.symlink_to(repo_loop_b)
        repo_loop_b.symlink_to(repo_loop_a)

        completed, failure = self.run_cli(
            "start",
            "--objective",
            "Inspect a repository",
            "--purpose",
            "Preserve current evidence",
            "--desired-state",
            "Inspection complete",
            "--success-criterion",
            "Evidence recorded",
            "--constraint",
            "Do not modify the repository",
            "--repo-root",
            str(repo_loop_a),
            "--authority",
            "read-only",
            "--idempotency-key",
            "looping-repo",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "invalid_repo_root")
        self.assertNotIn("Traceback", completed.stderr)

        completed, failure = self.run_cli(
            "list",
            "--repo-root",
            str(repo_loop_a),
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "invalid_repo_root")
        self.assertNotIn("Traceback", completed.stderr)

        db_loop_a = self.root / "db-loop-a"
        db_loop_b = self.root / "db-loop-b"
        db_loop_a.symlink_to(db_loop_b)
        db_loop_b.symlink_to(db_loop_a)
        targets_before = (os.readlink(db_loop_a), os.readlink(db_loop_b))
        completed, failure = self.run_cli(
            "list",
            expect_success=False,
            db_path=db_loop_a,
        )
        self.assertEqual(failure["error"]["code"], "invalid_db_path")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertTrue(db_loop_a.is_symlink())
        self.assertTrue(db_loop_b.is_symlink())
        self.assertEqual(
            (os.readlink(db_loop_a), os.readlink(db_loop_b)),
            targets_before,
        )

    def test_lease_contention_renewal_heartbeat_and_expiry_takeover(self) -> None:
        mission_id = self.mission_id()
        first = self.claim(mission_id, ttl="0.6")
        renewed = self.claim(mission_id, ttl="0.6")
        self.assertFalse(first["renewed"])
        self.assertTrue(renewed["renewed"])
        self.assertEqual(first["lease"]["generation"], 1)
        self.assertEqual(renewed["lease"]["generation"], 1)
        self.assertEqual(first["mission"]["lease_generation"], 1)
        self.assertEqual(first["mission"]["version"], 1)
        self.assertEqual(renewed["mission"]["lease_generation"], 1)

        _, contention = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "owner-b",
            "--expected-generation",
            "1",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(contention["error"]["code"], "lease_conflict")

        heartbeat = self.run_cli(
            "heartbeat",
            mission_id,
            "--owner",
            "owner-a",
            "--lease-generation",
            "1",
            "--ttl-seconds",
            "0.2",
        )[1]
        self.assertEqual(heartbeat["lease"]["owner"], "owner-a")
        self.assertEqual(heartbeat["lease"]["generation"], 1)

        time.sleep(0.3)
        takeover = self.claim(mission_id, owner="owner-b", ttl="30")
        self.assertFalse(takeover["renewed"])
        self.assertEqual(takeover["lease"]["owner"], "owner-b")
        self.assertEqual(takeover["lease"]["generation"], 2)
        self.assertEqual(takeover["mission"]["lease_generation"], 2)

    def test_mutation_timestamps_remain_ordered_after_wall_clock_rollback(self) -> None:
        mission_id = self.mission_id(key="wall-clock-rollback")
        self.claim(mission_id, owner="rollback-owner", ttl="3600")
        future_time = time.time() + 600.0
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                """
                UPDATE leases
                SET acquired_at = ?, heartbeat_at = ?, expires_at = ?
                WHERE mission_id = ?
                """,
                (future_time, future_time, future_time + 3600.0, mission_id),
            )
            connection.execute(
                "UPDATE missions SET updated_at = ? WHERE id = ?",
                (future_time, mission_id),
            )

        heartbeat = self.run_cli(
            "heartbeat",
            mission_id,
            "--owner",
            "rollback-owner",
            "--lease-generation",
            "1",
            "--ttl-seconds",
            "60",
        )[1]
        renewed = self.claim(mission_id, owner="rollback-owner", ttl="60")
        recorded = self.record(
            mission_id,
            owner="rollback-owner",
            summary="Logical time remains ordered",
            key="rollback-record",
        )
        transitioned = self.transition(
            mission_id,
            "verifying",
            owner="rollback-owner",
            key="rollback-transition",
        )
        released = self.run_cli(
            "release",
            mission_id,
            "--owner",
            "rollback-owner",
            "--lease-generation",
            "1",
        )[1]

        self.assertGreaterEqual(
            heartbeat["lease"]["heartbeat_at"],
            heartbeat["lease"]["acquired_at"],
        )
        self.assertGreater(
            heartbeat["lease"]["expires_at"],
            heartbeat["lease"]["heartbeat_at"],
        )
        self.assertTrue(renewed["renewed"])
        self.assertGreaterEqual(
            recorded["event"]["created_at"],
            heartbeat["lease"]["heartbeat_at"],
        )
        self.assertGreaterEqual(
            transitioned["event"]["created_at"],
            recorded["event"]["created_at"],
        )
        self.assertTrue(released["released"])
        shown = self.run_cli("show", mission_id)[1]
        self.assertIsNone(shown["active_lease"])
        self.assertEqual(shown["mission"]["state"], "verifying")

    def test_claim_rejects_a_stale_observed_mission_version(self) -> None:
        mission_id = self.mission_id(key="claim-version-cas")
        missing_version = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "missing-version-owner",
            "--expected-generation",
            "0",
            expect_success=False,
        )[1]
        self.assertEqual(missing_version["error"]["code"], "invalid_arguments")
        self.claim(
            mission_id,
            owner="old-owner",
            expected_generation=0,
            expected_version=1,
        )
        stale_observation = self.run_cli("show", mission_id)[1]
        self.assertEqual(stale_observation["mission"]["state"], "active")
        self.assertEqual(stale_observation["mission"]["version"], 1)

        waiting = self.transition(
            mission_id,
            "waiting",
            owner="old-owner",
            lease_generation=1,
            expected_version=1,
            key="old-owner-waiting",
        )
        self.assertEqual(waiting["mission"]["state"], "waiting")
        self.assertEqual(waiting["mission"]["version"], 2)
        self.assertIsNone(waiting["active_lease"])

        stale_claim = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "stale-observer",
            "--expected-generation",
            "1",
            "--expected-version",
            "1",
            expect_success=False,
        )[1]
        self.assertEqual(stale_claim["error"]["code"], "version_conflict")
        self.assertEqual(stale_claim["error"]["details"]["current_version"], 2)

        recovered = self.claim(
            mission_id,
            owner="reconciled-owner",
            expected_generation=1,
            expected_version=2,
        )
        self.assertEqual(recovered["mission"]["state"], "waiting")
        self.assertEqual(recovered["mission"]["version"], 2)
        self.assertEqual(recovered["lease"]["generation"], 2)

    def test_lease_generation_fences_claim_and_every_authorized_mutation(self) -> None:
        mission_id = self.mission_id(key="generation-fence")
        first = self.claim(
            mission_id,
            owner="execution-session",
            expected_generation=0,
        )
        self.assertEqual(first["lease"]["generation"], 1)

        stale_claim = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "execution-session",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )[1]
        self.assertEqual(stale_claim["error"]["code"], "lease_generation_conflict")
        self.assertEqual(stale_claim["error"]["details"]["current_generation"], 1)

        stale_commands = (
            (
                "heartbeat",
                mission_id,
                "--owner",
                "execution-session",
                "--lease-generation",
                "2",
            ),
            (
                "record",
                mission_id,
                "--owner",
                "execution-session",
                "--lease-generation",
                "2",
                "--kind",
                "progress",
                "--summary",
                "Must be fenced",
                "--idempotency-key",
                "stale-record",
            ),
            (
                "transition",
                mission_id,
                "--owner",
                "execution-session",
                "--lease-generation",
                "2",
                "--to",
                "waiting",
                "--expected-version",
                "1",
                "--summary",
                "Must be fenced",
                "--idempotency-key",
                "stale-transition",
            ),
            (
                "release",
                mission_id,
                "--owner",
                "execution-session",
                "--lease-generation",
                "2",
            ),
        )
        for command in stale_commands:
            with self.subTest(command=command[0]):
                failure = self.run_cli(*command, expect_success=False)[1]
                self.assertEqual(
                    failure["error"]["code"],
                    "lease_generation_conflict",
                )
                self.assertEqual(
                    failure["error"]["details"]["current_generation"],
                    1,
                )

        shown = self.run_cli("show", mission_id)[1]
        self.assertEqual(shown["mission"]["version"], 1)
        self.assertEqual(shown["events_total"], 0)
        self.assertEqual(shown["active_lease"]["generation"], 1)

        self.expire_lease(mission_id)
        reclaimed = self.claim(
            mission_id,
            owner="execution-session",
            expected_generation=1,
        )
        self.assertEqual(reclaimed["lease"]["generation"], 2)

        stale_reclaim = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "execution-session",
            "--expected-generation",
            "1",
            "--expected-version",
            "1",
            expect_success=False,
        )[1]
        self.assertEqual(stale_reclaim["error"]["code"], "lease_generation_conflict")
        stale_record = self.record(
            mission_id,
            owner="execution-session",
            lease_generation=1,
            key="old-execution-record",
            expect_success=False,
        )
        self.assertEqual(stale_record["error"]["code"], "lease_generation_conflict")

    def test_ttl_below_clock_resolution_fails_without_creating_a_lease(self) -> None:
        mission_id = self.mission_id(key="sub-clock-ttl")
        completed, failure = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "owner-a",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            "--ttl-seconds",
            "5e-324",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "invalid_input")
        self.assertNotIn("Traceback", completed.stderr)
        shown = self.run_cli("show", mission_id)[1]
        self.assertIsNone(shown["active_lease"])

    def test_lease_is_checked_after_waiting_for_writer_lock(self) -> None:
        mission_id = self.mission_id()
        self.claim(mission_id, owner="owner-a", ttl="2")

        lock_connection = sqlite3.connect(self.db, isolation_level=None, timeout=1)
        lock_connection.execute("BEGIN IMMEDIATE")
        process = subprocess.Popen(
            self.cli_command(
                "record",
                mission_id,
                "--owner",
                "owner-a",
                "--lease-generation",
                "1",
                "--kind",
                "progress",
                "--summary",
                "Must not commit after lease expiry",
                "--idempotency-key",
                "post-lock-expiry",
            ),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(0.4)
            waited_for_lock = process.poll() is None
            time.sleep(1.8)
        finally:
            lock_connection.rollback()
            lock_connection.close()

        stdout, stderr = process.communicate(timeout=5)
        self.assertTrue(waited_for_lock, f"process exited before lock release: {stderr}")
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(stdout, "")
        failure = json.loads(stderr)
        self.assertEqual(failure["error"]["code"], "lease_expired")

    def test_repo_reader_writer_leases_fail_closed_across_missions(self) -> None:
        reader_one = self.mission_id(key="reader-one", authority="read-only")
        reader_two = self.mission_id(key="reader-two", authority="read-only")
        writer = self.mission_id(key="writer", authority="local-write")
        with sqlite3.connect(self.db) as connection:
            connection.row_factory = sqlite3.Row
            identities = connection.execute(
                """
                SELECT id, repo_root, repo_device, repo_inode
                FROM missions WHERE id IN (?, ?)
                ORDER BY id
                """,
                (reader_one, writer),
            ).fetchall()
        self.assertEqual(identities[0]["repo_root"], identities[1]["repo_root"])
        self.assertEqual(identities[0]["repo_device"], identities[1]["repo_device"])
        self.assertEqual(identities[0]["repo_inode"], identities[1]["repo_inode"])

        self.claim(reader_one, owner="reader-owner-one")
        self.claim(reader_two, owner="reader-owner-two")
        renewed = self.claim(reader_one, owner="reader-owner-one")
        self.assertTrue(renewed["renewed"])

        writer_result, writer_conflict = self.run_cli(
            "claim",
            writer,
            "--owner",
            "writer-owner",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(writer_conflict["error"]["code"], "repo_lease_conflict")
        self.assertNotIn("reader-owner", writer_result.stderr)

        self.run_cli(
            "release",
            reader_two,
            "--owner",
            "reader-owner-two",
            "--lease-generation",
            "1",
        )
        self.expire_lease(reader_one)

        claimed_writer = self.claim(writer, owner="writer-owner")
        self.assertEqual(claimed_writer["lease"]["owner"], "writer-owner")
        renewed_writer = self.claim(writer, owner="writer-owner")
        self.assertTrue(renewed_writer["renewed"])

        blocked_reader = self.mission_id(key="blocked-reader", authority="read-only")
        reader_result, reader_conflict = self.run_cli(
            "claim",
            blocked_reader,
            "--owner",
            "reader-owner-three",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(reader_conflict["error"]["code"], "repo_lease_conflict")
        self.assertNotIn("writer-owner", reader_result.stderr)

        other_repo = self.root / "independent-worktree"
        other_repo.mkdir()
        independent_writer = self.mission_id(
            key="independent-writer",
            repo=other_repo,
            authority="local-write",
        )
        independent_claim = self.claim(independent_writer, owner="independent-owner")
        self.assertEqual(independent_claim["lease"]["owner"], "independent-owner")

    def test_repo_leases_conflict_for_ancestor_descendant_paths_only(self) -> None:
        parent_repo = self.root / "nested-parent"
        child_repo = parent_repo / "child"
        sibling_repo = self.root / "nested-sibling"
        child_repo.mkdir(parents=True)
        sibling_repo.mkdir()
        parent_writer = self.mission_id(key="parent-writer", repo=parent_repo)
        child_writer = self.mission_id(key="child-writer", repo=child_repo)
        sibling_writer = self.mission_id(key="sibling-writer", repo=sibling_repo)

        self.claim(parent_writer, owner="parent-writer-owner")
        completed, conflict = self.run_cli(
            "claim",
            child_writer,
            "--owner",
            "child-writer-owner",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(conflict["error"]["code"], "repo_lease_conflict")
        self.assertNotIn("parent-writer-owner", completed.stderr)
        sibling_claim = self.claim(sibling_writer, owner="sibling-writer-owner")
        self.assertEqual(sibling_claim["lease"]["generation"], 1)

        self.run_cli(
            "release",
            parent_writer,
            "--owner",
            "parent-writer-owner",
            "--lease-generation",
            "1",
        )
        child_claim = self.claim(child_writer, owner="child-writer-owner")
        self.assertEqual(child_claim["lease"]["generation"], 1)
        parent_reader = self.mission_id(
            key="parent-reader",
            repo=parent_repo,
            authority="read-only",
        )
        _, conflict = self.run_cli(
            "claim",
            parent_reader,
            "--owner",
            "parent-reader-owner",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(conflict["error"]["code"], "repo_lease_conflict")

        for mission_id, owner in (
            (child_writer, "child-writer-owner"),
            (sibling_writer, "sibling-writer-owner"),
        ):
            self.run_cli(
                "release",
                mission_id,
                "--owner",
                owner,
                "--lease-generation",
                "1",
            )
        child_reader = self.mission_id(
            key="child-reader",
            repo=child_repo,
            authority="read-only",
        )
        self.claim(parent_reader, owner="parent-reader-owner")
        concurrent_reader = self.claim(child_reader, owner="child-reader-owner")
        self.assertEqual(concurrent_reader["lease"]["generation"], 1)

    def test_claim_rejects_same_path_replacement_before_first_lease(self) -> None:
        replaceable_repo = self.root / "unclaimed-replaceable-repo"
        replaceable_repo.mkdir()
        mission_id = self.mission_id(
            key="unclaimed-replacement",
            repo=replaceable_repo,
        )
        moved_repo = self.root / "unclaimed-original-repo"
        replaceable_repo.rename(moved_repo)
        replaceable_repo.mkdir()

        completed, failure = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "replacement-observer",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertEqual(
            failure["error"]["details"]["reason"],
            "filesystem_identity_changed",
        )
        self.assertNotIn("Traceback", completed.stderr)
        shown = self.run_cli("show", mission_id)[1]
        self.assertIsNone(shown["active_lease"])
        self.assertEqual(shown["mission"]["lease_generation"], 0)

    def test_creation_identity_detects_same_inode_directory_reuse(self) -> None:
        replaceable_repo = self.root / "same-inode-repo"
        replaceable_repo.mkdir()
        started = self.start(key="same-inode-replacement", repo=replaceable_repo)
        mission_id = str(started["mission"]["id"])
        original_stat = replaceable_repo.stat()
        identify = LEDGER_MODULE["repository_creation_identity"]
        original_creation = identify(replaceable_repo, original_stat)

        ordinary_file = replaceable_repo / "ordinary-change"
        ordinary_file.write_text("normal repository content", encoding="utf-8")
        ordinary_file.unlink()
        self.assertEqual(
            identify(replaceable_repo, replaceable_repo.stat()),
            original_creation,
        )

        replaceable_repo.rmdir()
        replaceable_repo.mkdir()
        replacement_stat = replaceable_repo.stat()
        replacement_creation = identify(replaceable_repo, replacement_stat)
        self.assertNotEqual(replacement_creation, original_creation)

        # Some filesystems do not immediately reuse the inode. Normalize only
        # device/inode in the durable contract so the regression always isolates
        # the stable creation identity check that protects the reuse case.
        if (
            replacement_stat.st_dev != original_stat.st_dev
            or replacement_stat.st_ino != original_stat.st_ino
        ):
            with sqlite3.connect(self.db) as connection:
                row = connection.execute(
                    "SELECT start_payload_json FROM missions WHERE id = ?",
                    (mission_id,),
                ).fetchone()
                payload = json.loads(row[0])
                payload["repo_identity"]["device"] = str(replacement_stat.st_dev)
                payload["repo_identity"]["inode"] = str(replacement_stat.st_ino)
                canonical_payload = LEDGER_MODULE["canonical_json"](payload)
                connection.execute(
                    """
                    UPDATE missions
                    SET repo_device = ?, repo_inode = ?, start_payload_json = ?,
                        start_payload_hash = ?
                    WHERE id = ?
                    """,
                    (
                        str(replacement_stat.st_dev),
                        str(replacement_stat.st_ino),
                        canonical_payload,
                        LEDGER_MODULE["payload_hash"](canonical_payload),
                        mission_id,
                    ),
                )

        completed, failure = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "same-inode-observer",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertEqual(
            failure["error"]["details"]["reason"],
            "filesystem_creation_identity_changed",
        )
        self.assertNotIn("Traceback", completed.stderr)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "creation-identity source recovery simulation is Linux-specific",
    )
    def test_binding_reuses_recorded_creation_identity_kind(self) -> None:
        connection = LEDGER_MODULE["connect_database"](self.db)
        self.addCleanup(connection.close)
        identify = LEDGER_MODULE["repository_creation_identity"]
        function_globals = identify.__globals__
        original_handle = function_globals["linux_file_handle_creation_identity"]
        function_globals["linux_file_handle_creation_identity"] = lambda *_args: None
        try:
            started = LEDGER_MODULE["command_start"](
                connection,
                SimpleNamespace(
                    objective="Keep a stable repository binding",
                    purpose="Do not confuse capability recovery with repository replacement",
                    desired_state="The recorded identity source remains authoritative",
                    success_criterion=["The same repository can still be claimed"],
                    constraint=["Fail closed if the recorded source disappears"],
                    idempotency_key="recorded-identity-kind",
                    repo_root=str(self.repo),
                    authority="read-only",
                ),
            )
        finally:
            function_globals["linux_file_handle_creation_identity"] = original_handle

        mission = started["mission"]
        self.assertNotEqual(
            mission["repo_identity"]["creation"]["kind"],
            "linux-file-handle",
        )
        claimed = LEDGER_MODULE["command_claim"](
            connection,
            SimpleNamespace(
                mission_id=mission["id"],
                owner="identity-source-owner",
                expected_generation=0,
                expected_version=1,
                ttl_seconds=30.0,
            ),
        )
        self.assertEqual(claimed["lease"]["generation"], 1)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "deterministic creation-identity fallback simulation is Linux-specific",
    )
    def test_repo_start_fails_closed_without_stable_creation_identity(self) -> None:
        identify = LEDGER_MODULE["repository_creation_identity"]
        function_globals = identify.__globals__
        original_handle = function_globals["linux_file_handle_creation_identity"]
        original_birth = function_globals["linux_birth_time_creation_identity"]
        self.run_cli("list")
        connection = sqlite3.connect(self.db, isolation_level=None)
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        function_globals["linux_file_handle_creation_identity"] = lambda *_args: None
        function_globals["linux_birth_time_creation_identity"] = lambda *_args: None
        try:
            with self.assertRaises(LEDGER_MODULE["LedgerError"]) as raised:
                LEDGER_MODULE["command_start"](
                    connection,
                    SimpleNamespace(
                        objective="Unavailable identity must fail",
                        purpose="Prevent ambiguous repository replacement",
                        desired_state="No mission is created",
                        success_criterion=["Failure is structured"],
                        constraint=["Do not write project state"],
                        idempotency_key="unsupported-creation-identity",
                        repo_root=str(self.repo),
                        authority="read-only",
                    ),
                )
        finally:
            function_globals["linux_file_handle_creation_identity"] = original_handle
            function_globals["linux_birth_time_creation_identity"] = original_birth
        self.assertEqual(raised.exception.code, "repo_identity_unavailable")
        mission_count = connection.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
        self.assertEqual(mission_count, 0)

    @unittest.skipUnless(os.name == "posix", "symlink replacement requires POSIX")
    def test_claim_rejects_symlink_replacement_of_recorded_repo_root(self) -> None:
        replaceable_repo = self.root / "symlink-replaceable-repo"
        replaceable_repo.mkdir()
        mission_id = self.mission_id(
            key="symlink-replacement",
            repo=replaceable_repo,
        )
        moved_repo = self.root / "symlink-original-repo"
        replaceable_repo.rename(moved_repo)
        replaceable_repo.symlink_to(moved_repo, target_is_directory=True)

        completed, failure = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "symlink-observer",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertEqual(
            failure["error"]["details"]["reason"],
            "canonical_path_changed",
        )
        self.assertNotIn("Traceback", completed.stderr)

    def test_claim_renewal_revalidates_repo_binding_without_mutation(self) -> None:
        replaceable_repo = self.root / "renewal-replaceable-repo"
        replaceable_repo.mkdir()
        mission_id = self.mission_id(
            key="renewal-replacement",
            repo=replaceable_repo,
        )
        self.claim(mission_id, owner="renewal-owner")
        with sqlite3.connect(self.db) as connection:
            before = connection.execute(
                """
                SELECT missions.updated_at, missions.lease_generation,
                       leases.owner, leases.generation, leases.acquired_at,
                       leases.heartbeat_at, leases.expires_at
                FROM missions JOIN leases ON leases.mission_id = missions.id
                WHERE missions.id = ?
                """,
                (mission_id,),
            ).fetchone()
        moved_repo = self.root / "renewal-original-repo"
        replaceable_repo.rename(moved_repo)
        replaceable_repo.mkdir()

        completed, failure = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "renewal-owner",
            "--expected-generation",
            "1",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertNotIn("Traceback", completed.stderr)
        with sqlite3.connect(self.db) as connection:
            after = connection.execute(
                """
                SELECT missions.updated_at, missions.lease_generation,
                       leases.owner, leases.generation, leases.acquired_at,
                       leases.heartbeat_at, leases.expires_at
                FROM missions JOIN leases ON leases.mission_id = missions.id
                WHERE missions.id = ?
                """,
                (mission_id,),
            ).fetchone()
        self.assertEqual(after, before)

    def test_heartbeat_revalidates_repo_binding_without_extending_lease(self) -> None:
        replaceable_repo = self.root / "heartbeat-replaceable-repo"
        replaceable_repo.mkdir()
        mission_id = self.mission_id(
            key="heartbeat-replacement",
            repo=replaceable_repo,
        )
        self.claim(mission_id, owner="heartbeat-owner")
        with sqlite3.connect(self.db) as connection:
            before = connection.execute(
                """
                SELECT missions.state, missions.version, missions.updated_at,
                       leases.heartbeat_at, leases.expires_at,
                       (SELECT COUNT(*) FROM events
                        WHERE events.mission_id = missions.id)
                FROM missions JOIN leases ON leases.mission_id = missions.id
                WHERE missions.id = ?
                """,
                (mission_id,),
            ).fetchone()
        moved_repo = self.root / "heartbeat-original-repo"
        replaceable_repo.rename(moved_repo)
        replaceable_repo.mkdir()

        completed, failure = self.run_cli(
            "heartbeat",
            mission_id,
            "--owner",
            "heartbeat-owner",
            "--lease-generation",
            "1",
            "--ttl-seconds",
            "300",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertNotIn("Traceback", completed.stderr)

        completed, failure = self.run_cli(
            "record",
            mission_id,
            "--owner",
            "heartbeat-owner",
            "--lease-generation",
            "1",
            "--kind",
            "evidence",
            "--summary",
            "Must not record against a replaced repository",
            "--idempotency-key",
            "drifted-record",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertNotIn("Traceback", completed.stderr)

        completed, failure = self.run_cli(
            "transition",
            mission_id,
            "--owner",
            "heartbeat-owner",
            "--lease-generation",
            "1",
            "--to",
            "verifying",
            "--expected-version",
            "1",
            "--summary",
            "Must not transition against a replaced repository",
            "--idempotency-key",
            "drifted-transition",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertNotIn("Traceback", completed.stderr)

        with sqlite3.connect(self.db) as connection:
            after = connection.execute(
                """
                SELECT missions.state, missions.version, missions.updated_at,
                       leases.heartbeat_at, leases.expires_at,
                       (SELECT COUNT(*) FROM events
                        WHERE events.mission_id = missions.id)
                FROM missions JOIN leases ON leases.mission_id = missions.id
                WHERE missions.id = ?
                """,
                (mission_id,),
            ).fetchone()
        self.assertEqual(after, before)

        released = self.run_cli(
            "release",
            mission_id,
            "--owner",
            "heartbeat-owner",
            "--lease-generation",
            "1",
        )[1]
        self.assertTrue(released["released"])

    def test_repo_lease_fails_closed_on_inverse_same_path_replacement(self) -> None:
        replaceable_repo = self.root / "replaceable-repo"
        replaceable_repo.mkdir()
        first = self.mission_id(
            key="replacement-first",
            repo=replaceable_repo,
            authority="local-write",
        )
        self.claim(first, owner="first-writer")

        renamed_repo = self.root / "renamed-original-repo"
        replaceable_repo.rename(renamed_repo)
        replaceable_repo.mkdir()
        second = self.mission_id(
            key="replacement-second",
            repo=replaceable_repo,
            authority="local-write",
        )

        with sqlite3.connect(self.db) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, repo_root, repo_device, repo_inode
                FROM missions WHERE id IN (?, ?)
                ORDER BY id
                """,
                (first, second),
            ).fetchall()
        self.assertEqual(rows[0]["repo_root"], rows[1]["repo_root"])
        self.assertNotEqual(
            (rows[0]["repo_device"], rows[0]["repo_inode"]),
            (rows[1]["repo_device"], rows[1]["repo_inode"]),
        )

        completed, failure = self.run_cli(
            "claim",
            second,
            "--owner",
            "second-writer",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertEqual(
            failure["error"]["details"]["mission_id"],
            first,
        )
        self.assertNotIn("first-writer", completed.stderr)

        released = self.run_cli(
            "release",
            first,
            "--owner",
            "first-writer",
            "--lease-generation",
            "1",
        )[1]
        self.assertTrue(released["released"])
        claimed_second = self.claim(second, owner="second-writer")
        self.assertEqual(claimed_second["lease"]["generation"], 1)

    @unittest.skipUnless(os.name == "posix", "symlink replacement requires POSIX")
    def test_claim_revalidates_unrelated_active_binding_before_conflict_match(self) -> None:
        target_repo = self.root / "drift-target-repo"
        leased_repo = self.root / "formerly-independent-repo"
        target_repo.mkdir()
        leased_repo.mkdir()
        target = self.mission_id(key="drift-target", repo=target_repo)
        active = self.mission_id(key="drifted-active", repo=leased_repo)
        self.claim(active, owner="drifted-owner")

        moved_repo = self.root / "formerly-independent-original"
        leased_repo.rename(moved_repo)
        leased_repo.symlink_to(target_repo, target_is_directory=True)

        completed, failure = self.run_cli(
            "claim",
            target,
            "--owner",
            "target-owner",
            "--expected-generation",
            "0",
            "--expected-version",
            "1",
            expect_success=False,
        )
        self.assertEqual(failure["error"]["code"], "repo_binding_mismatch")
        self.assertEqual(failure["error"]["details"]["mission_id"], active)
        self.assertNotIn("drifted-owner", completed.stderr)

        released = self.run_cli(
            "release",
            active,
            "--owner",
            "drifted-owner",
            "--lease-generation",
            "1",
        )[1]
        self.assertTrue(released["released"])
        claimed_target = self.claim(target, owner="target-owner")
        self.assertEqual(claimed_target["lease"]["generation"], 1)

    def test_filesystem_case_detection_has_portable_deterministic_contract(self) -> None:
        detect = LEDGER_MODULE["filesystem_is_case_sensitive"]
        key_for = LEDGER_MODULE["filesystem_path_key"]
        paths_overlap = LEDGER_MODULE["repository_paths_overlap"]
        validate_separation = LEDGER_MODULE["validate_database_repo_separation"]
        path = Path("/Volume/CaseRepo")
        original_stat = SimpleNamespace(st_dev=7, st_ino=11)

        def insensitive_stat(candidate: Path) -> SimpleNamespace:
            self.assertEqual(str(candidate).casefold(), str(path).casefold())
            return SimpleNamespace(st_dev=7, st_ino=11)

        self.assertFalse(
            detect(
                path,
                original_stat,
                stat_path=insensitive_stat,
                exact_entry_exists=lambda *_args: False,
            )
        )
        self.assertEqual(
            key_for(path, False),
            key_for(Path("/volume/caserepo"), False),
        )

        def sensitive_stat(candidate: Path) -> SimpleNamespace:
            raise FileNotFoundError(candidate)

        self.assertTrue(
            detect(
                path,
                original_stat,
                stat_path=sensitive_stat,
                exact_entry_exists=lambda *_args: False,
            )
        )
        self.assertNotEqual(
            key_for(path, True),
            key_for(Path("/volume/caserepo"), True),
        )
        with self.assertRaises(LEDGER_MODULE["LedgerError"]):
            validate_separation(
                Path("/volume/caserepo/.state/objectives.sqlite3"),
                (("/Volume/CaseRepo", False),),
            )
        validate_separation(
            Path("/volume/caserepo/.state/objectives.sqlite3"),
            (("/Volume/CaseRepo", True),),
        )
        self.assertTrue(
            paths_overlap(
                "/Volume/CaseRepo",
                False,
                "/volume/caserepo/child",
                False,
            )
        )
        self.assertFalse(
            paths_overlap(
                "/Volume/CaseRepo",
                True,
                "/volume/caserepo/child",
                True,
            )
        )
        self.assertFalse(
            paths_overlap(
                "/Volume/CaseRepo/first",
                False,
                "/volume/caserepo/second",
                False,
            )
        )

    @unittest.skipUnless(os.name == "posix", "symlink aliases require POSIX semantics")
    def test_case_variant_symlink_does_not_poison_case_semantics(self) -> None:
        case_variant_alias = self.repo.with_name("Repo")
        case_variant_alias.symlink_to(self.repo, target_is_directory=True)

        started = self.start(key="case-variant-alias")
        mission = started["mission"]
        self.assertTrue(mission["repo_path_case_sensitive"])

        case_variant_alias.unlink()
        claimed = self.claim(str(mission["id"]))
        self.assertEqual(claimed["lease"]["generation"], 1)

    def test_case_only_distinct_directories_do_not_conflict_on_sensitive_filesystem(self) -> None:
        upper_repo = self.root / "CaseOnlyRepo"
        lower_repo = self.root / "caseonlyrepo"
        upper_repo.mkdir()
        try:
            lower_repo.mkdir()
        except FileExistsError:
            self.skipTest("filesystem does not permit distinct case-only directories")

        upper = self.start(key="case-sensitive-upper", repo=upper_repo)
        lower = self.start(key="case-sensitive-lower", repo=lower_repo)
        self.assertTrue(upper["mission"]["repo_path_case_sensitive"])
        self.assertTrue(lower["mission"]["repo_path_case_sensitive"])
        self.claim(str(upper["mission"]["id"]), owner="upper-owner")
        lower_claim = self.claim(str(lower["mission"]["id"]), owner="lower-owner")
        self.assertEqual(lower_claim["lease"]["owner"], "lower-owner")

    def test_case_insensitive_path_key_conflict_is_portably_simulated(self) -> None:
        first_repo = self.root / "SimulatedCaseRepo"
        second_repo = self.root / "simulatedcaserepo"
        first_repo.mkdir()
        try:
            second_repo.mkdir()
        except FileExistsError:
            self.skipTest("filesystem already provides real case-insensitive semantics")
        first = self.mission_id(key="simulated-case-first", repo=first_repo)
        second = self.mission_id(key="simulated-case-second", repo=second_repo)
        path_key = str(first_repo.resolve()).casefold()
        with sqlite3.connect(self.db, isolation_level=None) as connection:
            connection.row_factory = sqlite3.Row
            for mission_id in (first, second):
                row = connection.execute(
                    "SELECT start_payload_json FROM missions WHERE id = ?",
                    (mission_id,),
                ).fetchone()
                start_payload = json.loads(row["start_payload_json"])
                start_payload["repo_path"] = {
                    "case_sensitive": False,
                    "key": path_key,
                }
                canonical_payload = LEDGER_MODULE["canonical_json"](start_payload)
                connection.execute(
                    """
                    UPDATE missions
                    SET repo_path_key = ?, repo_case_sensitive = 0,
                        start_payload_json = ?, start_payload_hash = ?
                    WHERE id = ?
                    """,
                    (
                        path_key,
                        canonical_payload,
                        LEDGER_MODULE["payload_hash"](canonical_payload),
                        mission_id,
                    ),
                )

            command_claim = LEDGER_MODULE["command_claim"]
            function_globals = command_claim.__globals__
            original_case_detection = function_globals["filesystem_is_case_sensitive"]
            function_globals["filesystem_is_case_sensitive"] = lambda *_args: False
            try:
                first_claim = command_claim(
                    connection,
                    SimpleNamespace(
                        mission_id=first,
                        owner="case-owner-first",
                        expected_generation=0,
                        expected_version=1,
                        ttl_seconds=30.0,
                    ),
                )
                self.assertEqual(first_claim["lease"]["generation"], 1)
                with self.assertRaises(LEDGER_MODULE["LedgerError"]) as raised:
                    command_claim(
                        connection,
                        SimpleNamespace(
                            mission_id=second,
                            owner="case-owner-second",
                            expected_generation=0,
                            expected_version=1,
                            ttl_seconds=30.0,
                        ),
                    )
            finally:
                function_globals["filesystem_is_case_sensitive"] = (
                    original_case_detection
                )
        self.assertEqual(raised.exception.code, "repo_lease_conflict")
        listed = self.run_cli(
            "list",
            "--repo-root",
            str(first_repo).swapcase(),
        )[1]
        self.assertEqual(
            {mission["id"] for mission in listed["missions"]},
            {first, second},
        )

    @unittest.skipUnless(
        Path("/mnt/c/Users").is_dir() and Path("/mnt/c/users").is_dir(),
        "WSL /mnt/c case-insensitive path is unavailable",
    )
    def test_wsl_mnt_c_case_semantics_are_detected_when_available(self) -> None:
        detect = LEDGER_MODULE["filesystem_is_case_sensitive"]
        key_for = LEDGER_MODULE["filesystem_path_key"]
        upper = Path("/mnt/c/Users")
        lower = Path("/mnt/c/users")
        upper_stat = upper.stat()
        lower_stat = lower.stat()
        self.assertEqual(
            (upper_stat.st_dev, upper_stat.st_ino),
            (lower_stat.st_dev, lower_stat.st_ino),
        )
        self.assertFalse(detect(upper, upper_stat))
        self.assertEqual(key_for(upper, False), key_for(lower, False))

    def test_claim_renewal_heartbeat_and_record_refresh_mission_recency(self) -> None:
        older = self.mission_id(key="recency-older")
        newer = self.mission_id(key="recency-newer")
        listed = self.run_cli("list")[1]
        self.assertEqual(listed["missions"][0]["id"], newer)

        self.claim(older)
        listed = self.run_cli("list")[1]
        self.assertEqual(listed["missions"][0]["id"], older)

        newer_after_claim = self.mission_id(key="recency-after-claim")
        self.claim(older)
        listed = self.run_cli("list")[1]
        self.assertEqual(listed["missions"][0]["id"], older)

        newer_after_renewal = self.mission_id(key="recency-after-renewal")
        self.run_cli(
            "heartbeat",
            older,
            "--owner",
            "owner-a",
            "--lease-generation",
            "1",
        )
        listed = self.run_cli("list")[1]
        self.assertEqual(listed["missions"][0]["id"], older)

        newer_after_heartbeat = self.mission_id(key="recency-after-heartbeat")
        recorded = self.record(older, key="recency-record")
        listed = self.run_cli("list")[1]
        self.assertEqual(listed["missions"][0]["id"], older)
        self.assertEqual(listed["missions"][0]["version"], 1)

        with sqlite3.connect(self.db) as connection:
            mission_updated_at, event_created_at = connection.execute(
                """
                SELECT missions.updated_at, events.created_at
                FROM missions JOIN events ON events.mission_id = missions.id
                WHERE events.id = ?
                """,
                (recorded["event"]["id"],),
            ).fetchone()
        self.assertEqual(mission_updated_at, event_created_at)
        self.assertTrue(
            {newer, newer_after_claim, newer_after_renewal, newer_after_heartbeat}
            .issubset({mission["id"] for mission in listed["missions"]})
        )

    def test_record_requires_owner_and_has_canonical_idempotency(self) -> None:
        mission_id = self.mission_id()
        self.claim(mission_id)

        first = self.record(
            mission_id,
            kind="evidence",
            summary="Focused tests passed",
            metadata='{"b":2,"a":1}',
        )
        replay = self.record(
            mission_id,
            kind="evidence",
            summary="Focused tests passed",
            metadata='{"a":1,"b":2}',
        )
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(first["event"]["id"], replay["event"]["id"])
        self.assertEqual(first["event"]["lease_generation"], 1)

        conflict = self.record(
            mission_id,
            kind="evidence",
            summary="A mismatched replay",
            metadata='{"a":1,"b":2}',
            expect_success=False,
        )
        self.assertEqual(conflict["error"]["code"], "idempotency_conflict")

        wrong_owner = self.record(
            mission_id,
            owner="owner-b",
            key="wrong-owner",
            expect_success=False,
        )
        self.assertEqual(wrong_owner["error"]["code"], "lease_not_owned")

    def test_record_replay_uses_historical_fencing_generation(self) -> None:
        mission_id = self.mission_id(key="historical-record-generation")
        self.claim(mission_id, owner="execution-one")
        recorded = self.record(
            mission_id,
            owner="execution-one",
            lease_generation=1,
            summary="Historical checkpoint",
            key="historical-record",
        )
        self.run_cli(
            "release",
            mission_id,
            "--owner",
            "execution-one",
            "--lease-generation",
            "1",
        )
        self.claim(mission_id, owner="execution-two", expected_generation=1)

        replay = self.record(
            mission_id,
            owner="execution-one",
            lease_generation=1,
            summary="Historical checkpoint",
            key="historical-record",
        )
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["event"]["id"], recorded["event"]["id"])
        mismatched_generation = self.record(
            mission_id,
            owner="execution-one",
            lease_generation=2,
            summary="Historical checkpoint",
            key="historical-record",
            expect_success=False,
        )
        self.assertEqual(
            mismatched_generation["error"]["code"],
            "idempotency_conflict",
        )

    def test_pathological_metadata_errors_are_structured_and_nonmutating(self) -> None:
        mission_id = self.mission_id(key="pathological-metadata")
        self.claim(mission_id)
        with sqlite3.connect(self.db) as connection:
            before = connection.execute(
                """
                SELECT updated_at,
                       (SELECT COUNT(*) FROM events WHERE mission_id = missions.id)
                FROM missions WHERE id = ?
                """,
                (mission_id,),
            ).fetchone()

        cases = {
            "huge-integer": '{"value":' + ("9" * 5000) + "}",
            "deeply-nested": '{"value":' + ("[" * 2000) + "0" + ("]" * 2000) + "}",
        }
        for name, metadata in cases.items():
            with self.subTest(case=name):
                completed, failure = self.run_cli(
                    "record",
                    mission_id,
                    "--owner",
                    "owner-a",
                    "--lease-generation",
                    "1",
                    "--kind",
                    "progress",
                    "--summary",
                    "Must not be recorded",
                    "--metadata-json",
                    metadata,
                    "--idempotency-key",
                    f"invalid-metadata-{name}",
                    expect_success=False,
                )
                self.assertEqual(
                    failure["error"]["code"],
                    "invalid_metadata_json",
                )
                self.assertNotIn("Traceback", completed.stderr)

        with sqlite3.connect(self.db) as connection:
            after = connection.execute(
                """
                SELECT updated_at,
                       (SELECT COUNT(*) FROM events WHERE mission_id = missions.id)
                FROM missions WHERE id = ?
                """,
                (mission_id,),
            ).fetchone()
        self.assertEqual(after, before)

    def test_invalid_transition_is_rejected_without_state_change(self) -> None:
        mission_id = self.mission_id()
        self.claim(mission_id)
        stale = self.transition(
            mission_id,
            "waiting",
            expected_version=2,
            key="stale-version",
            expect_success=False,
        )
        self.assertEqual(stale["error"]["code"], "version_conflict")
        self.assertEqual(stale["error"]["details"]["current_version"], 1)
        self.record(mission_id, kind="evidence", summary="Evidence exists")

        invalid = self.transition(
            mission_id,
            "complete",
            completion_summary="Done",
            expect_success=False,
        )
        self.assertEqual(invalid["error"]["code"], "invalid_transition")

        show = self.run_cli("show", mission_id)[1]
        self.assertEqual(show["mission"]["state"], "active")
        self.assertEqual(show["mission"]["version"], 1)
        self.assertIsNotNone(show["active_lease"])

    def test_completion_requires_verifying_evidence_and_summary(self) -> None:
        mission_id = self.mission_id()
        self.claim(mission_id)
        verifying = self.transition(mission_id, "verifying")
        self.assertFalse(verifying["event_effect"]["lease_released"])
        self.assertIsNotNone(verifying["active_lease"])

        no_evidence = self.transition(
            mission_id,
            "complete",
            expected_version=2,
            key="complete-1",
            completion_summary="All criteria met",
            expect_success=False,
        )
        self.assertEqual(no_evidence["error"]["code"], "completion_evidence_required")

        self.record(
            mission_id,
            kind="evidence",
            summary="All success criteria verified",
            key="evidence-1",
        )
        missing_summary = self.transition(
            mission_id,
            "complete",
            expected_version=2,
            key="complete-without-summary",
            expect_success=False,
        )
        self.assertEqual(missing_summary["error"]["code"], "invalid_input")

        completed = self.transition(
            mission_id,
            "complete",
            expected_version=2,
            key="complete-1",
            completion_summary="All criteria met",
        )
        self.assertTrue(completed["event_effect"]["lease_released"])
        self.assertIsNone(completed["active_lease"])
        self.assertEqual(completed["mission"]["state"], "complete")
        self.assertEqual(completed["mission"]["version"], 3)
        self.assertEqual(completed["mission"]["completion_summary"], "All criteria met")

        replay = self.transition(
            mission_id,
            "complete",
            expected_version=2,
            key="complete-1",
            completion_summary="All criteria met",
        )
        self.assertTrue(replay["replayed"])

        mismatch = self.transition(
            mission_id,
            "complete",
            expected_version=2,
            summary="Different replay",
            key="complete-1",
            completion_summary="All criteria met",
            expect_success=False,
        )
        self.assertEqual(mismatch["error"]["code"], "idempotency_conflict")
        version_payload_mismatch = self.transition(
            mission_id,
            "complete",
            expected_version=3,
            key="complete-1",
            completion_summary="All criteria met",
            expect_success=False,
        )
        self.assertEqual(
            version_payload_mismatch["error"]["code"],
            "idempotency_conflict",
        )

    def test_transition_replay_separates_historical_effect_from_current_lease(self) -> None:
        mission_id = self.mission_id(key="transition-response-start")
        self.claim(mission_id)
        waiting = self.transition(
            mission_id,
            "waiting",
            key="historical-wait",
        )
        self.assertTrue(waiting["event_effect"]["lease_released"])
        self.assertEqual(waiting["mission"]["state"], "waiting")
        self.assertIsNone(waiting["active_lease"])
        self.assertNotIn("lease_released", waiting)

        reclaimed = self.claim(mission_id)
        self.assertEqual(reclaimed["lease"]["generation"], 2)
        resumed = self.transition(
            mission_id,
            "active",
            expected_version=2,
            key="resume-after-wait",
        )
        self.assertFalse(resumed["event_effect"]["lease_released"])
        self.assertEqual(resumed["mission"]["state"], "active")
        self.assertIsNotNone(resumed["active_lease"])

        replay = self.transition(
            mission_id,
            "waiting",
            lease_generation=1,
            expected_version=1,
            key="historical-wait",
        )
        self.assertTrue(replay["replayed"])
        self.assertTrue(replay["event_effect"]["lease_released"])
        self.assertEqual(replay["event"]["state_to"], "waiting")
        self.assertEqual(replay["mission"]["state"], "active")
        self.assertEqual(replay["mission"]["version"], 3)
        self.assertIsNotNone(replay["active_lease"])
        self.assertEqual(replay["active_lease"]["generation"], 2)
        self.assertNotIn("lease_released", replay)

    def test_released_state_rejects_a_fabricated_old_generation_lease(self) -> None:
        mission_id = self.mission_id(key="fabricated-released-lease")
        self.claim(mission_id)
        self.transition(
            mission_id,
            "waiting",
            key="release-before-fabrication",
        )
        with sqlite3.connect(self.db) as connection:
            updated_at = connection.execute(
                "SELECT updated_at FROM missions WHERE id = ?",
                (mission_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO leases (
                    mission_id, owner, generation,
                    acquired_at, heartbeat_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    mission_id,
                    "fabricated-owner",
                    1,
                    updated_at,
                    updated_at,
                    updated_at + 3600,
                ),
            )
        source_before = self.database_file_set()

        completed, failure = self.run_cli(
            "show",
            mission_id,
            expect_success=False,
        )

        self.assertEqual(failure["error"]["code"], "database_error")
        self.assertEqual(failure["error"]["details"]["table"], "leases")
        self.assertEqual(failure["error"]["details"]["field"], "generation")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)

    def test_completion_rejects_evidence_from_before_latest_verifying_cycle(self) -> None:
        mission_id = self.mission_id()
        self.claim(mission_id)
        self.record(
            mission_id,
            kind="evidence",
            summary="Evidence recorded before verification",
            key="evidence-before-verifying",
        )
        self.transition(mission_id, "verifying", key="verifying-cycle-one")

        before_cycle = self.transition(
            mission_id,
            "complete",
            expected_version=2,
            key="complete-with-pre-verifying-evidence",
            completion_summary="Should not complete",
            expect_success=False,
        )
        self.assertEqual(before_cycle["error"]["code"], "completion_evidence_required")

        self.record(
            mission_id,
            kind="evidence",
            summary="Evidence for the first verification cycle",
            key="evidence-cycle-one",
        )
        self.transition(
            mission_id,
            "active",
            expected_version=2,
            key="verification-failed-back-to-active",
        )
        self.transition(
            mission_id,
            "verifying",
            expected_version=3,
            key="verifying-cycle-two",
        )

        prior_cycle = self.transition(
            mission_id,
            "complete",
            expected_version=4,
            key="complete-with-prior-cycle-evidence",
            completion_summary="Should still not complete",
            expect_success=False,
        )
        self.assertEqual(prior_cycle["error"]["code"], "completion_evidence_required")

        self.record(
            mission_id,
            kind="evidence",
            summary="Fresh evidence for the latest verification cycle",
            key="evidence-cycle-two",
        )
        completed = self.transition(
            mission_id,
            "complete",
            expected_version=4,
            key="complete-cycle-two",
            completion_summary="Latest-cycle evidence verified",
        )
        self.assertEqual(completed["mission"]["state"], "complete")

    def test_completion_requires_evidence_from_current_lease_generation(self) -> None:
        mission_id = self.mission_id()
        first_claim = self.claim(mission_id, owner="owner-a")
        self.assertEqual(first_claim["lease"]["generation"], 1)
        self.transition(
            mission_id,
            "verifying",
            owner="owner-a",
            key="verifying-generation-one",
        )
        old_evidence = self.record(
            mission_id,
            owner="owner-a",
            kind="evidence",
            summary="Evidence under the first lease",
            key="evidence-generation-one",
        )
        self.assertEqual(old_evidence["event"]["lease_generation"], 1)

        self.expire_lease(mission_id)
        takeover = self.claim(mission_id, owner="owner-b")
        self.assertEqual(takeover["lease"]["generation"], 2)

        stale_generation = self.transition(
            mission_id,
            "complete",
            owner="owner-b",
            expected_version=2,
            key="complete-with-old-generation",
            completion_summary="Should not complete",
            expect_success=False,
        )
        self.assertEqual(
            stale_generation["error"]["code"],
            "completion_evidence_required",
        )

        new_evidence = self.record(
            mission_id,
            owner="owner-b",
            kind="evidence",
            summary="Evidence reconciled under the takeover lease",
            key="evidence-generation-two",
        )
        self.assertEqual(new_evidence["event"]["lease_generation"], 2)
        completed = self.transition(
            mission_id,
            "complete",
            owner="owner-b",
            expected_version=2,
            key="complete-generation-two",
            completion_summary="Takeover evidence verified",
        )
        self.assertEqual(completed["mission"]["state"], "complete")
        self.assertEqual(completed["event"]["lease_generation"], 2)

    def test_terminal_missions_are_immutable(self) -> None:
        mission_id = self.mission_id()
        self.claim(mission_id)
        self.transition(mission_id, "verifying")
        self.record(mission_id, kind="evidence", summary="Criteria verified")
        self.transition(
            mission_id,
            "complete",
            expected_version=2,
            completion_summary="Verified complete",
        )

        _, claim_failure = self.run_cli(
            "claim",
            mission_id,
            "--owner",
            "owner-a",
            "--expected-generation",
            "1",
            "--expected-version",
            "3",
            expect_success=False,
        )
        self.assertEqual(claim_failure["error"]["code"], "terminal_state")

        transition_failure = self.transition(
            mission_id,
            "active",
            expected_version=3,
            key="after-complete",
            expect_success=False,
        )
        self.assertEqual(transition_failure["error"]["code"], "terminal_state")

        record_failure = self.record(
            mission_id,
            key="after-complete-record",
            expect_success=False,
        )
        self.assertEqual(record_failure["error"]["code"], "terminal_state")
        evidence_replay = self.record(
            mission_id,
            kind="evidence",
            summary="Criteria verified",
            key="record-1",
        )
        self.assertTrue(evidence_replay["replayed"])
        self.assertEqual(evidence_replay["event"]["lease_generation"], 1)

    def test_waiting_blocked_interrupted_abandoned_and_complete_release_lease(self) -> None:
        direct_states = ("waiting", "blocked", "interrupted", "abandoned")
        for index, state_name in enumerate(direct_states):
            with self.subTest(state=state_name):
                mission_id = self.mission_id(key=f"state-start-{index}")
                self.claim(mission_id)
                result = self.transition(
                    mission_id,
                    state_name,
                    key=f"state-transition-{index}",
                )
                self.assertTrue(result["event_effect"]["lease_released"])
                self.assertIsNone(result["active_lease"])
                show = self.run_cli("show", mission_id)[1]
                self.assertIsNone(show["active_lease"])

        mission_id = self.mission_id(key="blocked-waiting-start")
        self.claim(mission_id)
        self.transition(mission_id, "blocked", key="to-blocked")
        self.claim(mission_id)
        waiting = self.transition(
            mission_id,
            "waiting",
            expected_version=2,
            key="blocked-to-waiting",
        )
        self.assertEqual(waiting["mission"]["state"], "waiting")
        self.assertTrue(waiting["event_effect"]["lease_released"])
        self.assertIsNone(waiting["active_lease"])

    def test_release_requires_current_owner(self) -> None:
        mission_id = self.mission_id(key="release-recency-first")
        self.claim(mission_id)
        _, wrong_owner = self.run_cli(
            "release",
            mission_id,
            "--owner",
            "owner-b",
            "--lease-generation",
            "1",
            expect_success=False,
        )
        self.assertEqual(wrong_owner["error"]["code"], "lease_not_owned")

        newer_id = self.mission_id(key="release-recency-second")
        released = self.run_cli(
            "release",
            mission_id,
            "--owner",
            "owner-a",
            "--lease-generation",
            "1",
        )[1]
        self.assertTrue(released["released"])
        show = self.run_cli("show", mission_id)[1]
        self.assertIsNone(show["active_lease"])
        listed = self.run_cli("list")[1]
        self.assertEqual(listed["missions"][0]["id"], mission_id)
        self.assertIn(newer_id, {mission["id"] for mission in listed["missions"]})

        _, second_release = self.run_cli(
            "release",
            mission_id,
            "--owner",
            "owner-a",
            "--lease-generation",
            "1",
            expect_success=False,
        )
        self.assertEqual(second_release["error"]["code"], "lease_required")

    def test_show_and_filtered_list_are_machine_readable_and_reconcilable(self) -> None:
        other_repo = self.root / "other-repo"
        other_repo.mkdir()
        first_id = self.mission_id(key="first")
        second_id = self.mission_id(key="second", repo=other_repo, authority="read-only")

        self.claim(first_id)
        self.record(first_id, kind="checkpoint", summary="Inspected current diff", key="cp")
        self.record(first_id, kind="evidence", summary="Validation passed", key="ev")
        self.transition(first_id, "waiting", summary="Awaiting material input", key="wait")

        shown = self.run_cli("show", first_id, "--events-limit", "2")[1]
        self.assertEqual(shown["mission"]["id"], first_id)
        self.assertEqual(
            shown["mission"]["purpose"],
            "Preserve the user's intended result and decision principles",
        )
        self.assertEqual(
            shown["mission"]["success_criteria"],
            ["Focused validation passes", "The diff matches the objective"],
        )
        self.assertEqual(
            shown["mission"]["constraints"],
            ["Do not perform external writes", "Preserve unrelated repository changes"],
        )
        self.assertEqual(shown["events_total"], 3)
        self.assertEqual(shown["events_returned"], 2)
        event_ids = [event["id"] for event in shown["events"]]
        self.assertEqual(event_ids, sorted(event_ids))
        self.assertTrue(all(event["lease_generation"] == 1 for event in shown["events"]))
        self.assertEqual(shown["events"][-1]["state_to"], "waiting")
        self.assertIsNone(shown["active_lease"])
        self.assertEqual(shown["mission"]["lease_generation"], 1)

        waiting = self.run_cli(
            "list",
            "--state",
            "waiting",
            "--repo-root",
            str(self.repo),
        )[1]
        self.assertEqual(waiting["count"], 1)
        self.assertEqual(waiting["total_count"], 1)
        self.assertFalse(waiting["truncated"])
        self.assertEqual(waiting["missions"][0]["id"], first_id)
        self.assertEqual(
            waiting["missions"][0]["purpose"],
            "Preserve the user's intended result and decision principles",
        )
        self.assertEqual(
            waiting["missions"][0]["constraints"],
            ["Do not perform external writes", "Preserve unrelated repository changes"],
        )
        self.assertNotIn("events", waiting["missions"][0])

        active_other = self.run_cli(
            "list",
            "--state",
            "active",
            "--repo-root",
            str(other_repo),
        )[1]
        self.assertEqual(active_other["count"], 1)
        self.assertEqual(active_other["missions"][0]["id"], second_id)

        renamed_repo = self.root / "renamed-repo"
        self.repo.rename(renamed_repo)
        moved = self.run_cli(
            "list",
            "--repo-root",
            str(renamed_repo),
        )[1]
        self.assertEqual(moved["count"], 1)
        self.assertEqual(moved["missions"][0]["id"], first_id)

    def test_json_wire_output_survives_ascii_python_io_encoding(self) -> None:
        ascii_env = {**os.environ, "PYTHONIOENCODING": "ascii"}
        completed, started = self.run_cli(
            "start",
            "--objective",
            "검증된 결과를 전달한다",
            "--purpose",
            "사용자의 판단 원칙을 보존한다",
            "--desired-state",
            "결과가 검증되었다",
            "--success-criterion",
            "검증이 통과한다",
            "--constraint",
            "외부 쓰기를 하지 않는다",
            "--repo-root",
            str(self.repo),
            "--authority",
            "read-only",
            "--idempotency-key",
            "korean-wire-start",
            env=ascii_env,
        )
        self.assertIn("\\u", completed.stdout)
        self.assertNotIn("검증된", completed.stdout)
        self.assertEqual(started["mission"]["objective"], "검증된 결과를 전달한다")

        mission_id = started["mission"]["id"]
        shown_completed, shown = self.run_cli(
            "show",
            str(mission_id),
            env=ascii_env,
        )
        self.assertIn("\\u", shown_completed.stdout)
        self.assertEqual(shown["mission"]["purpose"], "사용자의 판단 원칙을 보존한다")

        invalid_repo = self.root / "없는저장소"
        failed, failure = self.run_cli(
            "start",
            "--objective",
            "실패 경로",
            "--purpose",
            "오류도 JSON이어야 한다",
            "--desired-state",
            "도달하지 않음",
            "--success-criterion",
            "오류가 구조화된다",
            "--constraint",
            "변경하지 않는다",
            "--repo-root",
            str(invalid_repo),
            "--authority",
            "read-only",
            "--idempotency-key",
            "korean-wire-failure",
            expect_success=False,
            env=ascii_env,
        )
        self.assertEqual(failure["error"]["code"], "invalid_repo_root")
        self.assertIn("\\u", failed.stderr)
        self.assertNotIn("Traceback", failed.stderr)

    def test_show_and_list_use_explicit_read_transactions(self) -> None:
        mission_id = self.mission_id()
        connection = sqlite3.connect(self.db, isolation_level=None)
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        trace: list[str] = []
        connection.set_trace_callback(trace.append)

        command_list = LEDGER_MODULE["command_list"]
        listed = command_list(
            connection,
            SimpleNamespace(state=None, repo_root=None, limit=100),
        )
        self.assertEqual(listed["count"], 1)
        self.assertEqual(trace[0], "BEGIN")
        self.assertEqual(trace[-1], "COMMIT")

        trace.clear()
        command_show = LEDGER_MODULE["command_show"]
        shown = command_show(
            connection,
            SimpleNamespace(mission_id=mission_id, events_limit=100),
        )
        self.assertEqual(shown["mission"]["id"], mission_id)
        self.assertEqual(trace[0], "BEGIN")
        self.assertEqual(trace[-1], "COMMIT")

    def test_identified_validation_uses_one_snapshot_during_concurrent_write(
        self,
    ) -> None:
        mission_id = self.mission_id(key="validation-snapshot")
        self.claim(mission_id, owner="snapshot-owner")
        reader = sqlite3.connect(self.db, isolation_level=None)
        writer = sqlite3.connect(self.db, isolation_level=None)
        self.addCleanup(reader.close)
        self.addCleanup(writer.close)
        reader.row_factory = sqlite3.Row
        writer.row_factory = sqlite3.Row
        self.assertEqual(
            reader.execute("PRAGMA journal_mode").fetchone()[0].lower(),
            "wal",
        )

        validator = LEDGER_MODULE["validate_identified_ledger"]
        function_globals = validator.__globals__
        original_validate_mission = function_globals["validate_mission_row"]
        transition = LEDGER_MODULE["command_transition"]
        transition_committed = False

        def interleaving_validate_mission(row: sqlite3.Row) -> None:
            nonlocal transition_committed
            original_validate_mission(row)
            if transition_committed:
                return
            transition_committed = True
            transition(
                writer,
                SimpleNamespace(
                    mission_id=mission_id,
                    owner="snapshot-owner",
                    lease_generation=1,
                    to_state="waiting",
                    expected_version=1,
                    summary="Pause after validation snapshot starts",
                    completion_summary=None,
                    idempotency_key="snapshot-transition",
                ),
            )

        function_globals["validate_mission_row"] = interleaving_validate_mission
        try:
            repo_bindings = validator(reader)
        finally:
            function_globals["validate_mission_row"] = original_validate_mission
        self.assertTrue(transition_committed)
        repo_stat = self.repo.stat()
        self.assertEqual(
            repo_bindings,
            (
                (
                    str(self.repo.resolve()),
                    LEDGER_MODULE["filesystem_is_case_sensitive"](
                        self.repo.resolve(),
                        repo_stat,
                    ),
                ),
            ),
        )
        current_state = writer.execute(
            "SELECT state FROM missions WHERE id = ?",
            (mission_id,),
        ).fetchone()[0]
        self.assertEqual(current_state, "waiting")

    @unittest.skipUnless(os.name == "posix", "POSIX permission modes are unavailable")
    def test_local_state_uses_restrictive_permissions_and_expected_schema(self) -> None:
        self.run_cli("list")
        directory_mode = stat.S_IMODE(self.db.parent.stat().st_mode)
        database_mode = stat.S_IMODE(self.db.stat().st_mode)
        self.assertEqual(directory_mode, 0o700)
        self.assertEqual(database_mode, 0o600)

        with sqlite3.connect(self.db) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
            mission_foreign_keys = connection.execute(
                "PRAGMA foreign_key_list(events)"
            ).fetchall()
            mission_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(missions)")
            }
        self.assertTrue({"missions", "events", "leases"}.issubset(tables))
        self.assertEqual(journal_mode.lower(), "wal")
        self.assertEqual(application_id, APPLICATION_ID)
        self.assertEqual(schema_version, 1)
        self.assertTrue(mission_foreign_keys)
        self.assertTrue(
            {"repo_creation_kind", "repo_creation_value"}.issubset(mission_columns)
        )
        header = self.db.read_bytes()[:100]
        self.assertEqual(int.from_bytes(header[60:64], "big"), 1)
        self.assertEqual(int.from_bytes(header[68:72], "big"), APPLICATION_ID)

    def test_preflight_clone_ignores_project_scoped_temp_directory(self) -> None:
        self.mission_id(key="external-preflight-clone")
        project_temp = self.repo / ".tmp"
        project_temp.mkdir()
        inspect_database = LEDGER_MODULE["inspect_recovered_database"]
        preflight_root = LEDGER_MODULE["ensure_private_preflight_workspace"]()
        workspace_entries_before = {path.name for path in preflight_root.iterdir()}
        function_globals = inspect_database.__globals__
        original_inspect_clone = function_globals["inspect_recovered_clone"]
        original_tempdir = tempfile.tempdir
        observed_clone_paths: list[Path] = []

        def observe_clone(clone_path: Path) -> object:
            observed_clone_paths.append(clone_path)
            return original_inspect_clone(clone_path)

        function_globals["inspect_recovered_clone"] = observe_clone
        tempfile.tempdir = str(project_temp)
        try:
            inspect_database(self.db)
        finally:
            tempfile.tempdir = original_tempdir
            function_globals["inspect_recovered_clone"] = original_inspect_clone

        self.assertTrue(observed_clone_paths)
        self.assertTrue(
            all(path.is_relative_to(preflight_root) for path in observed_clone_paths)
        )
        self.assertTrue(
            all(not path.is_relative_to(self.repo) for path in observed_clone_paths)
        )
        self.assertEqual(list(project_temp.iterdir()), [])
        self.assertEqual(
            {path.name for path in preflight_root.iterdir()},
            workspace_entries_before,
        )

    @unittest.skipUnless(os.name == "posix", "POSIX permission modes are unavailable")
    def test_unsafe_identified_main_and_sidecar_modes_fail_before_source_open(self) -> None:
        mission_id = self.mission_id(key="unsafe-ledger-modes")
        keeper = sqlite3.connect(self.db, isolation_level=None)
        self.addCleanup(keeper.close)
        keeper.execute("PRAGMA wal_autocheckpoint = 0")
        keeper.execute("BEGIN IMMEDIATE")
        keeper.execute(
            "UPDATE missions SET updated_at = updated_at WHERE id = ?",
            (mission_id,),
        )
        keeper.commit()
        wal_path = Path(str(self.db) + "-wal")
        shm_path = Path(str(self.db) + "-shm")
        self.assertTrue(wal_path.exists())
        self.assertTrue(shm_path.exists())
        for path in (self.db, wal_path, shm_path):
            os.chmod(path, 0o644)
        wal_source_before = self.database_file_set()

        completed, failure = self.run_cli("show", mission_id, expect_success=False)
        self.assertEqual(failure["error"]["code"], "unsafe_database_permissions")
        self.assertEqual(
            set(failure["error"]["details"]["files"]),
            {"main", "-wal", "-shm"},
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), wal_source_before)

        keeper.close()
        for path in (self.db, wal_path, shm_path):
            if path.exists():
                os.chmod(path, 0o600)
        self.run_cli("show", mission_id)
        with sqlite3.connect(self.db, isolation_level=None) as connection:
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA journal_mode = PERSIST")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE missions SET updated_at = updated_at WHERE id = ?",
                (mission_id,),
            )
            connection.commit()
        journal_path = Path(str(self.db) + "-journal")
        self.assertTrue(journal_path.exists())
        os.chmod(journal_path, 0o644)
        journal_source_before = self.database_file_set()

        completed, failure = self.run_cli("show", mission_id, expect_success=False)
        self.assertEqual(failure["error"]["code"], "unsafe_database_permissions")
        self.assertEqual(
            failure["error"]["details"]["files"],
            {"-journal": "0644"},
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), journal_source_before)

    @unittest.skipUnless(os.name == "posix", "hot-journal preservation requires POSIX")
    def test_foreign_hot_journal_is_rejected_without_byte_mutation(self) -> None:
        db_path = self.root / "foreign-hot.sqlite3"
        with sqlite3.connect(db_path) as connection:
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("CREATE TABLE unrelated(id INTEGER PRIMARY KEY, value BLOB)")
            connection.executemany(
                "INSERT INTO unrelated(value) VALUES (?)",
                [(b"x" * 4096,) for _ in range(80)],
            )
            connection.execute("PRAGMA application_id = 305419896")
            connection.execute("PRAGMA user_version = 1")

        crash = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import os
import sqlite3
import sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute('PRAGMA journal_mode = DELETE')
connection.execute('PRAGMA synchronous = FULL')
connection.execute('PRAGMA cache_size = 1')
connection.execute('BEGIN IMMEDIATE')
connection.execute('UPDATE unrelated SET value = randomblob(4096)')
os._exit(0)
""",
                str(db_path),
            ],
            check=False,
        )
        self.assertEqual(crash.returncode, 0)
        journal_path = Path(str(db_path) + "-journal")
        self.assertTrue(journal_path.exists())
        self.assertGreater(journal_path.stat().st_size, 512)
        main_before = db_path.read_bytes()
        journal_before = journal_path.read_bytes()
        mode_before = stat.S_IMODE(db_path.stat().st_mode)

        completed, failure = self.run_cli(
            "list",
            expect_success=False,
            db_path=db_path,
        )
        self.assertEqual(failure["error"]["code"], "database_identity_mismatch")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(db_path.read_bytes(), main_before)
        self.assertTrue(journal_path.exists())
        self.assertEqual(journal_path.read_bytes(), journal_before)
        self.assertEqual(stat.S_IMODE(db_path.stat().st_mode), mode_before)

    @unittest.skipUnless(os.name == "posix", "crash recovery requires POSIX")
    def test_identified_ledger_recovers_hot_rollback_journal(self) -> None:
        mission_id = self.mission_id(key="own-hot-rollback")
        original_objective = self.run_cli("show", mission_id)[1]["mission"]["objective"]
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0].lower(),
                "delete",
            )

        crash = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import os
import sqlite3
import sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute('PRAGMA journal_mode = DELETE')
connection.execute('PRAGMA synchronous = FULL')
connection.execute('PRAGMA cache_size = 1')
connection.execute('BEGIN IMMEDIATE')
connection.execute("UPDATE missions SET objective = 'uncommitted-crash-value'")
connection.execute('CREATE TABLE crash_fill(value BLOB)')
for _ in range(80):
    connection.execute('INSERT INTO crash_fill(value) VALUES (randomblob(4096))')
os._exit(0)
""",
                str(self.db),
            ],
            check=False,
        )
        self.assertEqual(crash.returncode, 0)
        journal_path = Path(str(self.db) + "-journal")
        self.assertTrue(journal_path.exists())
        self.assertGreater(journal_path.stat().st_size, 512)

        shown = self.run_cli("show", mission_id)[1]
        self.assertEqual(shown["mission"]["objective"], original_objective)
        self.assertFalse(journal_path.exists())
        with sqlite3.connect(self.db) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema WHERE type = 'table'"
                )
            }
        self.assertNotIn("crash_fill", tables)

    @unittest.skipUnless(os.name == "posix", "WAL crash recovery requires POSIX")
    def test_identified_ledger_reads_committed_wal_after_crash(self) -> None:
        mission_id = self.mission_id(key="own-wal-crash")
        header_before = self.db.read_bytes()[:100]
        self.assertEqual(int.from_bytes(header_before[68:72], "big"), APPLICATION_ID)

        crash = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import os
import sqlite3
import sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute('PRAGMA wal_autocheckpoint = 0')
connection.execute('BEGIN IMMEDIATE')
connection.execute("UPDATE missions SET updated_at = 2000000000.0")
connection.commit()
os._exit(0)
""",
                str(self.db),
            ],
            check=False,
        )
        self.assertEqual(crash.returncode, 0)
        wal_path = Path(str(self.db) + "-wal")
        self.assertTrue(wal_path.exists())
        self.assertGreater(wal_path.stat().st_size, 0)

        shown = self.run_cli("show", mission_id)[1]
        self.assertEqual(shown["mission"]["updated_at"], "2033-05-18T03:33:20Z")
        header_after = self.db.read_bytes()[:100]
        self.assertEqual(int.from_bytes(header_after[60:64], "big"), 1)
        self.assertEqual(int.from_bytes(header_after[68:72], "big"), APPLICATION_ID)

    @unittest.skipUnless(os.name == "posix", "WAL crash preservation requires POSIX")
    def test_future_schema_only_in_wal_is_rejected_without_source_mutation(self) -> None:
        self.mission_id(key="future-version-in-wal")
        self.crash_wal_pragma("PRAGMA user_version = 99")

        header = self.db.read_bytes()[:100]
        self.assertEqual(int.from_bytes(header[60:64], "big"), 1)
        self.assertEqual(int.from_bytes(header[68:72], "big"), APPLICATION_ID)
        wal_path = Path(str(self.db) + "-wal")
        self.assertTrue(wal_path.exists())
        self.assertGreater(wal_path.stat().st_size, 0)
        source_before = self.database_file_set()

        completed, failure = self.run_cli("list", expect_success=False)
        self.assertEqual(failure["error"]["code"], "unsupported_schema_version")
        self.assertEqual(failure["error"]["details"]["current_version"], 99)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)

    @unittest.skipUnless(os.name == "posix", "WAL crash preservation requires POSIX")
    def test_foreign_application_only_in_wal_is_rejected_without_source_mutation(
        self,
    ) -> None:
        self.mission_id(key="foreign-application-in-wal")
        foreign_application_id = 0x12345678
        self.crash_wal_pragma(
            f"PRAGMA application_id = {foreign_application_id}"
        )

        header = self.db.read_bytes()[:100]
        self.assertEqual(int.from_bytes(header[68:72], "big"), APPLICATION_ID)
        source_before = self.database_file_set()

        completed, failure = self.run_cli("list", expect_success=False)
        self.assertEqual(failure["error"]["code"], "database_identity_mismatch")
        self.assertEqual(
            failure["error"]["details"]["application_id"],
            foreign_application_id,
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)

    @unittest.skipUnless(os.name == "posix", "WAL crash preservation requires POSIX")
    def test_corrupt_committed_wal_is_rejected_without_source_mutation(self) -> None:
        self.mission_id(key="corrupt-schema-in-wal")
        crash = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import os
import sqlite3
import sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute('PRAGMA wal_autocheckpoint = 0')
connection.execute('PRAGMA writable_schema = ON')
connection.execute('BEGIN IMMEDIATE')
connection.execute(
    "UPDATE sqlite_schema SET sql = 'CREATE TABLE missions(' WHERE name = 'missions'"
)
connection.commit()
os._exit(0)
""",
                str(self.db),
            ],
            check=False,
        )
        self.assertEqual(crash.returncode, 0)
        source_before = self.database_file_set()
        self.assertIn("-wal", source_before)

        completed, failure = self.run_cli("list", expect_success=False)
        self.assertEqual(failure["error"]["code"], "database_error")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)

    def test_snapshot_capture_retries_once_then_fails_closed(self) -> None:
        self.mission_id(key="changing-during-preflight")
        inspect_database = LEDGER_MODULE["inspect_recovered_database"]
        function_globals = inspect_database.__globals__
        original_capture = function_globals["capture_database_state"]
        capture_calls = 0

        def changing_capture(db_path: Path) -> object:
            nonlocal capture_calls
            captured = original_capture(db_path)
            capture_calls += 1
            if capture_calls in (1, 3):
                current = db_path.stat()
                os.utime(
                    db_path,
                    ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000_000),
                )
            return captured

        function_globals["capture_database_state"] = changing_capture
        try:
            with self.assertRaises(LEDGER_MODULE["LedgerError"]) as raised:
                inspect_database(self.db)
        finally:
            function_globals["capture_database_state"] = original_capture
        self.assertEqual(raised.exception.code, "database_busy")
        self.assertEqual(capture_calls, 4)

    def test_future_schema_version_fails_clearly(self) -> None:
        self.db.parent.mkdir()
        with sqlite3.connect(self.db) as connection:
            connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            connection.execute("PRAGMA user_version = 99")

        _, failure = self.run_cli("list", expect_success=False)
        self.assertEqual(failure["error"]["code"], "unsupported_schema_version")
        self.assertEqual(failure["error"]["details"]["current_version"], 99)
        self.assertEqual(failure["error"]["details"]["supported_version"], 1)

    @unittest.skipUnless(os.name == "posix", "POSIX mode preservation is unavailable")
    def test_identified_partial_schema_is_rejected_without_source_mutation(self) -> None:
        self.mission_id(key="partial-schema")
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0],
                "delete",
            )
            connection.execute("DROP INDEX events_mission_created_idx")
        os.chmod(self.db, 0o640)
        journal_mode_before = self.readonly_journal_mode()
        source_before = self.database_file_set()

        completed, failure = self.run_cli("list", expect_success=False)
        self.assertEqual(failure["error"]["code"], "invalid_ledger_schema")
        self.assertIn(
            "index:events_mission_created_idx",
            failure["error"]["details"]["missing"],
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)
        self.assertEqual(self.readonly_journal_mode(), journal_mode_before)

    @unittest.skipUnless(os.name == "posix", "POSIX mode preservation is unavailable")
    def test_corrupt_persisted_rows_are_structured_and_source_preserving(self) -> None:
        mission_id = self.mission_id(key="corrupt-persisted-row")
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0],
                "delete",
            )
            original = connection.execute(
                """
                SELECT success_criteria_json, start_payload_hash
                FROM missions WHERE id = ?
                """,
                (mission_id,),
            ).fetchone()
            connection.execute(
                "UPDATE missions SET success_criteria_json = '{' WHERE id = ?",
                (mission_id,),
            )
        os.chmod(self.db, 0o640)
        journal_mode_before = self.readonly_journal_mode()
        invalid_json_before = self.database_file_set()

        completed, failure = self.run_cli("list", expect_success=False)
        self.assertEqual(failure["error"]["code"], "database_error")
        self.assertEqual(
            failure["error"]["details"]["field"],
            "success_criteria_json",
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), invalid_json_before)
        self.assertEqual(self.readonly_journal_mode(), journal_mode_before)

        with sqlite3.connect(self.db) as connection:
            connection.execute(
                """
                UPDATE missions
                SET success_criteria_json = ?, start_payload_hash = ?
                WHERE id = ?
                """,
                (original[0], "0" * 64, mission_id),
            )
        hash_mismatch_before = self.database_file_set()
        completed, failure = self.run_cli("show", mission_id, expect_success=False)
        self.assertEqual(failure["error"]["code"], "database_error")
        self.assertEqual(
            failure["error"]["details"]["field"],
            "start_payload_hash",
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), hash_mismatch_before)
        self.assertEqual(self.readonly_journal_mode(), journal_mode_before)

    def test_corrupt_creation_identity_kind_is_rejected_as_persisted_data(self) -> None:
        mission_id = self.mission_id(key="corrupt-creation-kind")
        with sqlite3.connect(self.db) as connection:
            connection.execute("PRAGMA journal_mode = DELETE")
            row = connection.execute(
                "SELECT start_payload_json FROM missions WHERE id = ?",
                (mission_id,),
            ).fetchone()
            payload = json.loads(row[0])
            payload["repo_identity"]["creation"]["kind"] = "unsupported-kind"
            canonical_payload = LEDGER_MODULE["canonical_json"](payload)
            connection.execute(
                """
                UPDATE missions
                SET repo_creation_kind = ?, start_payload_json = ?,
                    start_payload_hash = ?
                WHERE id = ?
                """,
                (
                    "unsupported-kind",
                    canonical_payload,
                    LEDGER_MODULE["payload_hash"](canonical_payload),
                    mission_id,
                ),
            )
        source_before = self.database_file_set()

        completed, failure = self.run_cli("show", mission_id, expect_success=False)
        self.assertEqual(failure["error"]["code"], "database_error")
        self.assertEqual(
            failure["error"]["details"]["field"],
            "repo_creation_kind",
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)

    def test_impossible_persisted_state_is_rejected_by_transition_replay(self) -> None:
        mission_id = self.mission_id(key="impossible-state")
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0],
                "delete",
            )
            connection.execute(
                "UPDATE missions SET state = 'abandoned' WHERE id = ?",
                (mission_id,),
            )
        source_before = self.database_file_set()

        completed, failure = self.run_cli("show", mission_id, expect_success=False)
        self.assertEqual(failure["error"]["code"], "database_error")
        self.assertEqual(failure["error"]["details"]["field"], "state")
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)

    def test_complete_state_without_fresh_evidence_is_rejected_as_corrupt(self) -> None:
        mission_id = self.mission_id(key="missing-completion-evidence")
        self.claim(mission_id, owner="completion-owner")
        self.transition(
            mission_id,
            "verifying",
            owner="completion-owner",
            key="enter-verifying",
        )
        self.record(
            mission_id,
            owner="completion-owner",
            kind="evidence",
            summary="Completion proof",
            key="completion-proof",
        )
        self.transition(
            mission_id,
            "complete",
            owner="completion-owner",
            expected_version=2,
            completion_summary="All success criteria verified",
            key="complete-with-proof",
        )
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                """
                DELETE FROM events
                WHERE mission_id = ? AND action = 'record' AND kind = 'evidence'
                """,
                (mission_id,),
            )
        source_before = self.database_file_set()

        completed, failure = self.run_cli("show", mission_id, expect_success=False)
        self.assertEqual(failure["error"]["code"], "database_error")
        self.assertEqual(
            failure["error"]["details"]["field"],
            "completion_evidence",
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.database_file_set(), source_before)

    @unittest.skipUnless(os.name == "posix", "POSIX mode preservation is unavailable")
    def test_unrelated_sqlite_is_rejected_without_persistent_mutation(self) -> None:
        cases = (
            ("versioned-unidentified", 0, 1, None),
            ("unversioned-nonempty", 0, 0, "CREATE TABLE unrelated(value TEXT)"),
            (
                "unversioned-view-only",
                0,
                0,
                "CREATE VIEW unrelated_view AS SELECT 1 AS value",
            ),
            ("foreign-application", 0x12345678, 1, "CREATE TABLE unrelated(value TEXT)"),
        )
        for name, application_id, schema_version, create_object_sql in cases:
            with self.subTest(case=name):
                db_path = self.root / f"{name}.sqlite3"
                with sqlite3.connect(db_path) as connection:
                    connection.execute("PRAGMA journal_mode = DELETE")
                    if create_object_sql:
                        connection.execute(create_object_sql)
                    connection.execute(f"PRAGMA application_id = {application_id}")
                    connection.execute(f"PRAGMA user_version = {schema_version}")
                os.chmod(db_path, 0o640)

                before_mode = stat.S_IMODE(db_path.stat().st_mode)
                with sqlite3.connect(db_path) as connection:
                    before = {
                        "application_id": connection.execute(
                            "PRAGMA application_id"
                        ).fetchone()[0],
                        "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
                        "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                        "objects": {
                            tuple(row)
                            for row in connection.execute(
                                """
                                SELECT type, name, sql FROM sqlite_schema
                                WHERE name NOT GLOB 'sqlite_*'
                                """
                            )
                        },
                    }

                _, failure = self.run_cli(
                    "list",
                    expect_success=False,
                    db_path=db_path,
                )
                self.assertEqual(
                    failure["error"]["code"],
                    "database_identity_mismatch",
                )

                with sqlite3.connect(db_path) as connection:
                    after = {
                        "application_id": connection.execute(
                            "PRAGMA application_id"
                        ).fetchone()[0],
                        "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
                        "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                        "objects": {
                            tuple(row)
                            for row in connection.execute(
                                """
                                SELECT type, name, sql FROM sqlite_schema
                                WHERE name NOT GLOB 'sqlite_*'
                                """
                            )
                        },
                    }
                self.assertEqual(after, before)
                self.assertEqual(stat.S_IMODE(db_path.stat().st_mode), before_mode)
                object_names = {row[1] for row in after["objects"]}
                self.assertFalse({"missions", "events", "leases"} & object_names)

    @unittest.skipUnless(os.name == "posix", "POSIX mode preservation is unavailable")
    def test_malformed_database_failure_is_structured_and_nonmutating(self) -> None:
        db_path = self.root / "malformed.sqlite3"
        original = b"not-a-sqlite-database"
        db_path.write_bytes(original)
        os.chmod(db_path, 0o640)

        _, failure = self.run_cli(
            "list",
            expect_success=False,
            db_path=db_path,
        )
        self.assertEqual(failure["error"]["code"], "database_error")
        self.assertEqual(db_path.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(db_path.stat().st_mode), 0o640)


if __name__ == "__main__":
    unittest.main()
