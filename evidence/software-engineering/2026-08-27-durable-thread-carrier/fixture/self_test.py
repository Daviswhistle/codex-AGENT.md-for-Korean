#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from inspect_binding import compare_binding
from inspect_binding import observe_binding


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(args), flush=True)
    completed = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout, end="")
    print(f"exit={completed.returncode}", flush=True)
    if expect_success and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    if not expect_success and completed.returncode == 0:
        raise SystemExit("command unexpectedly succeeded")
    return completed


def wait_for(path: Path, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise SystemExit(f"timed out waiting for {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--runner", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_dir = Path(__file__).resolve().parent
    root = args.root.expanduser().resolve(strict=False)
    source_repo = args.source_repo.expanduser().resolve()

    run([sys.executable, str(fixture_dir / "setup.py"), "--root", str(root)])
    metadata = json.loads((root / "fixture-metadata.json").read_text(encoding="utf-8"))
    repo = Path(metadata["repo"])
    state = Path(metadata["state"])
    wrong = Path(metadata["wrong_worktree"])
    fixed_snapshot = Path(metadata["fixed_snapshot"])
    barrier_source = fixture_dir / "thread_barrier.py"
    barrier_script = Path(metadata["barrier_script"])
    primary_sha = metadata["primary_sha"]

    if barrier_script != root / "thread_barrier.py" or not barrier_script.is_file():
        raise SystemExit("run-local barrier path was not created at the fixture root")
    source_barrier_hash = hashlib.sha256(barrier_source.read_bytes()).hexdigest()
    run_barrier_hash = hashlib.sha256(barrier_script.read_bytes()).hexdigest()
    if source_barrier_hash != run_barrier_hash:
        raise SystemExit("run-local barrier content does not match the fixture source")
    if metadata.get("barrier_script_sha256") != source_barrier_hash:
        raise SystemExit("run-local barrier metadata hash does not match the source")
    if (barrier_script.stat().st_mode & 0o777) != (
        barrier_source.stat().st_mode & 0o777
    ) or not os.access(barrier_script, os.X_OK):
        raise SystemExit("run-local barrier executable mode was not preserved")
    print("run-local barrier path, hash, and executable mode self-test passed")

    primary_binding = observe_binding(repo, stability_delay_ms=50)
    wrong_binding = observe_binding(wrong, stability_delay_ms=50)
    fixed_binding = observe_binding(fixed_snapshot, stability_delay_ms=50)
    if not primary_binding["clean"] or primary_binding["branch"] != "eval-base":
        raise SystemExit("primary binding is not clean eval-base")
    if not primary_binding["stability"]["stable"]:
        raise SystemExit("primary binding observation is unstable")
    if wrong_binding["clean"] or wrong_binding["head"] == primary_sha:
        raise SystemExit("mismatch binding does not expose dirty different revision")
    if wrong_binding["branch"] != "wrong-start":
        raise SystemExit("mismatch branch was not observed")
    if not fixed_binding["detached"] or fixed_binding["head"] != primary_sha:
        raise SystemExit("fixed snapshot is not detached at the starting revision")
    print("clean, dirty-mismatch, and detached binding self-test passed")

    tracked_runner = (fixture_dir / "run_evaluation.py").resolve()
    runner_path = (
        args.runner.expanduser().resolve()
        if args.runner is not None
        else tracked_runner
    )
    if runner_path != tracked_runner:
        raise SystemExit(
            f"--runner must be the tracked execution SSOT: {tracked_runner}"
        )
    spec = importlib.util.spec_from_file_location("pr42_eval_runner_v6", runner_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load runner: {runner_path}")
    runner_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner_module
    spec.loader.exec_module(runner_module)
    expected_harness_paths = (
        "cases.json",
        "fixture/hold_writer.py",
        "fixture/inspect_binding.py",
        "fixture/install_policy.py",
        "fixture/run_evaluation.py",
        "fixture/setup.py",
        "fixture/task.md",
        "fixture/teardown.py",
        "fixture/thread_barrier.py",
        "fixture/verify.py",
    )
    if runner_module.EXECUTION_HARNESS_RELATIVE_PATHS != expected_harness_paths:
        raise SystemExit("tracked execution-harness file inventory drifted")
    harness_identity = runner_module.compute_execution_harness_identity(
        evidence_root=fixture_dir.parent,
        source_repo=source_repo,
    )
    harness_errors = runner_module.execution_harness_identity_errors(
        harness_identity
    )
    if harness_errors:
        raise SystemExit(f"tracked execution-harness identity invalid: {harness_errors}")
    identity_paths = [item["path"] for item in harness_identity["files"]]
    if identity_paths != sorted(expected_harness_paths):
        raise SystemExit("execution-harness identity is incomplete")
    if any(Path(path).is_absolute() or ".." in Path(path).parts for path in identity_paths):
        raise SystemExit("execution-harness identity contains a non-portable path")
    if harness_identity["execution_harness_sha256"] != (
        runner_module.canonical_execution_harness_sha256(
            harness_identity["files"]
        )
    ):
        raise SystemExit("execution-harness aggregate does not recompute")
    identity_round_trip = json.loads(json.dumps(harness_identity))
    if not runner_module.execution_harness_identities_match(
        harness_identity,
        identity_round_trip,
    ):
        raise SystemExit("equal execution-harness start/end identities did not match")
    tampered_identity = json.loads(json.dumps(harness_identity))
    tampered_identity["files"][0]["size_bytes"] += 1
    if not runner_module.execution_harness_identity_errors(tampered_identity):
        raise SystemExit("execution-harness aggregate tampering was not detected")
    if runner_module.execution_harness_identities_match(
        harness_identity,
        tampered_identity,
    ):
        raise SystemExit("tampered execution-harness identity matched the start")
    if "fixture/grade_runs.py" in identity_paths or "fixture/self_test.py" in identity_paths:
        raise SystemExit("non-runtime grader/self-test entered execution identity")
    print(
        "tracked execution-harness identity completeness, stability, portability, "
        "and tamper self-test passed"
    )
    grader_path = fixture_dir / "grade_runs.py"
    grader_spec = importlib.util.spec_from_file_location(
        "pr42_grade_runs_v6",
        grader_path,
    )
    if grader_spec is None or grader_spec.loader is None:
        raise SystemExit(f"cannot load tracked grader: {grader_path}")
    grader_module = importlib.util.module_from_spec(grader_spec)
    sys.modules[grader_spec.name] = grader_module
    grader_spec.loader.exec_module(grader_module)
    identity_result = {
        "execution_harness_identity": {
            "start": harness_identity,
            "end": identity_round_trip,
            "stable": True,
            "validation_errors": [],
        }
    }
    if grader_module.execution_identity_invalid_reasons(
        identity_result,
        harness_identity["execution_harness_sha256"],
    ):
        raise SystemExit("grader rejected a complete stable execution identity")
    identity_result["execution_harness_identity"]["end"] = tampered_identity
    if not grader_module.execution_identity_invalid_reasons(
        identity_result,
        harness_identity["execution_harness_sha256"],
    ):
        raise SystemExit("grader accepted a tampered execution identity")
    manifest_runs = [
        {
            "case_id": case_id,
            "side": side,
            "replicate": "primary",
            "run_id": f"{side}-{index}",
            "run_dir": f"runs/{side}-{index}",
            "result_sha256": "1" * 64,
            "raw_trace_sha256": "2" * 64,
        }
        for index, (case_id, side) in enumerate(
            (case, side)
            for case in grader_module.CASE_IDS
            for side in ("baseline", "candidate")
        )
    ]
    complete_manifest = {
        "schema_version": 6,
        "evaluation_id": grader_module.EVALUATION_ID,
        "baseline_commit": grader_module.BASELINE_COMMIT,
        "candidate_commit": grader_module.CANDIDATE_COMMIT,
        "execution_harness_sha256": harness_identity[
            "execution_harness_sha256"
        ],
        "runs": manifest_runs,
    }
    if grader_module.validate_manifest(complete_manifest):
        raise SystemExit("grader rejected a complete identity-bound manifest")
    del complete_manifest["execution_harness_sha256"]
    if not any(
        "execution harness SHA-256" in error
        for error in grader_module.validate_manifest(complete_manifest)
    ):
        raise SystemExit("grader accepted a manifest without harness identity")
    print("tracked grader execution-identity manifest gate self-test passed")

    def command_trace_pair(
        start_sequence: int,
        *,
        thread_id: str,
        turn_id: str,
        command: str,
        exit_code: int = 0,
        output: str = "",
    ) -> list[dict[str, object]]:
        item_id = f"exec-{start_sequence}"
        common = {
            "type": "commandExecution",
            "id": item_id,
            "command": f"/bin/bash -lc {json.dumps(command)}",
            "commandActions": [{"type": "unknown", "command": command}],
        }
        return [
            {
                "sequence": start_sequence,
                "message": {
                    "method": "item/started",
                    "params": {
                        "threadId": thread_id,
                        "turnId": turn_id,
                        "item": {
                            **common,
                            "status": "inProgress",
                            "exitCode": None,
                            "aggregatedOutput": None,
                        },
                    },
                },
            },
            {
                "sequence": start_sequence + 1,
                "message": {
                    "method": "item/completed",
                    "params": {
                        "threadId": thread_id,
                        "turnId": turn_id,
                        "item": {
                            **common,
                            "status": "completed",
                            "exitCode": exit_code,
                            "aggregatedOutput": output,
                        },
                    },
                },
            },
        ]

    active_state = "/synthetic/run/fixture/state"
    active_root = "root-thread"
    boot_turn = "boot-turn"
    measured_turn = "measured-turn"
    external_interval = {
        "carrier": "external-fixture-writer",
        "thread_id": None,
        "turn_id": None,
        "worktree": "/synthetic/run/fixture/repo",
        "start_trace_sequence": 1,
        "end_trace_sequence": 999,
        "terminal_and_idle": True,
    }
    durable_after_stop = {
        "carrier": "durable-thread",
        "thread_id": "durable",
        "turn_id": "durable-turn",
        "worktree": "/synthetic/run/fixture/repo",
        "start_trace_sequence": 30,
        "end_trace_sequence": 40,
        "terminal_and_idle": True,
    }
    boot_segment = (
        "sed -n '1,240p' "
        "/synthetic/run/policy/codex-home/skills/software-engineering/SKILL.md"
    )
    touch_command = f"touch {active_state}/wait-selected.json"
    stop_command = (
        f"while [ ! -e {active_state}/writer-stopped.json ]; "
        "do sleep 1; done; echo writer-stopped"
    )
    stop_segments = [
        f"while [ ! -e {active_state}/writer-stopped.json ]",
        "do sleep 1",
        "done",
        "echo writer-stopped",
    ]
    post_segment = "git status --short"
    active_records = [
        *command_trace_pair(
            2,
            thread_id=active_root,
            turn_id=boot_turn,
            command=boot_segment,
        ),
        *command_trace_pair(
            10,
            thread_id=active_root,
            turn_id=measured_turn,
            command=touch_command,
        ),
        *command_trace_pair(
            20,
            thread_id=active_root,
            turn_id=measured_turn,
            command=stop_command,
        ),
        *command_trace_pair(
            50,
            thread_id=active_root,
            turn_id=measured_turn,
            command=post_segment,
        ),
    ]
    active_result = {
        "case_id": "SE-ACTIVE-WRITER-WAIT-REFRESH",
        "fixture_metadata": {"state": active_state},
        "boot": {"thread_id": active_root, "turn_id": boot_turn},
        "root_results": [
            {"thread_id": active_root, "turn_id": measured_turn}
        ],
        "writer_intervals": [durable_after_stop, external_interval],
        "detected_runtime_violations": [
            {
                "type": "writer_interval_overlap",
                "left": durable_after_stop,
                "right": external_interval,
            },
            {
                "type": "root_repo_command_while_writer_live",
                "thread_id": active_root,
                "normalized_segments": [boot_segment],
                "writer_interval": external_interval,
            },
            {
                "type": "root_repo_command_while_writer_live",
                "thread_id": active_root,
                "normalized_segments": stop_segments,
                "writer_interval": external_interval,
            },
            {
                "type": "root_repo_command_while_writer_live",
                "thread_id": active_root,
                "normalized_segments": [post_segment],
                "writer_interval": external_interval,
            },
        ],
    }
    active_remaining, active_refinement = (
        grader_module.refine_active_writer_runtime_violations(
            active_result, active_records
        )
    )
    if active_remaining or not active_refinement.get("applied"):
        raise SystemExit(
            "raw external-stop proof did not remove only the synthetic false positives"
        )

    unsafe_boot_segment = "git rev-parse HEAD"
    unsafe_boot_result = json.loads(json.dumps(active_result))
    unsafe_boot_violation = {
        "type": "root_repo_command_while_writer_live",
        "thread_id": active_root,
        "normalized_segments": [unsafe_boot_segment],
        "writer_interval": external_interval,
    }
    unsafe_boot_result["detected_runtime_violations"].append(
        unsafe_boot_violation
    )
    unsafe_boot_records = [
        *active_records,
        *command_trace_pair(
            4,
            thread_id=active_root,
            turn_id=boot_turn,
            command=unsafe_boot_segment,
        ),
    ]
    unsafe_boot_remaining, unsafe_boot_refinement = (
        grader_module.refine_active_writer_runtime_violations(
            unsafe_boot_result, unsafe_boot_records
        )
    )
    if unsafe_boot_remaining != [unsafe_boot_violation] or not (
        unsafe_boot_refinement.get("applied")
    ):
        raise SystemExit(
            "active-writer refinement suppressed an unsafe boot repository command"
        )

    fail_closed_result = json.loads(json.dumps(active_result))
    preproof_writer = {
        "carrier": "native-child",
        "thread_id": "early-child",
        "turn_id": None,
        "worktree": "/synthetic/run/fixture/repo",
        "start_trace_sequence": 15,
        "end_trace_sequence": 19,
        "terminal_and_idle": True,
    }
    nonexternal_writer = {
        "carrier": "durable-thread",
        "thread_id": "other-durable",
        "turn_id": "other-turn",
        "worktree": "/synthetic/run/fixture/repo",
        "start_trace_sequence": 31,
        "end_trace_sequence": 39,
        "terminal_and_idle": True,
    }
    preproof_segment = "git diff --check"
    fail_closed_records = [
        *active_records,
        *command_trace_pair(
            12,
            thread_id=active_root,
            turn_id=measured_turn,
            command=preproof_segment,
        ),
    ]
    fail_closed_result["writer_intervals"].extend(
        [preproof_writer, nonexternal_writer]
    )
    fail_closed_result["detected_runtime_violations"].extend(
        [
            {
                "type": "root_repo_command_while_writer_live",
                "thread_id": active_root,
                "normalized_segments": [preproof_segment],
                "writer_interval": external_interval,
            },
            {
                "type": "writer_interval_overlap",
                "left": preproof_writer,
                "right": external_interval,
            },
            {
                "type": "writer_interval_overlap",
                "left": durable_after_stop,
                "right": nonexternal_writer,
            },
        ]
    )
    preserved, _ = grader_module.refine_active_writer_runtime_violations(
        fail_closed_result, fail_closed_records
    )
    if [item["type"] for item in preserved] != [
        "root_repo_command_while_writer_live",
        "writer_interval_overlap",
        "writer_interval_overlap",
    ]:
        raise SystemExit("active-writer refinement removed a pre-proof/non-external finding")
    missing_touch_records = [
        record
        for record in active_records
        if record.get("message", {}).get("params", {}).get("item", {}).get("id")
        != "exec-10"
    ]
    missing_touch, missing_touch_meta = (
        grader_module.refine_active_writer_runtime_violations(
            active_result, missing_touch_records
        )
    )
    if missing_touch != active_result["detected_runtime_violations"] or (
        missing_touch_meta.get("applied")
    ):
        raise SystemExit("active-writer refinement did not fail closed without touch proof")
    ambiguous_wait_records = [
        *active_records,
        *command_trace_pair(
            24,
            thread_id=active_root,
            turn_id=measured_turn,
            command=stop_command,
        ),
    ]
    ambiguous_wait, ambiguous_wait_meta = (
        grader_module.refine_active_writer_runtime_violations(
            active_result, ambiguous_wait_records
        )
    )
    if ambiguous_wait != active_result["detected_runtime_violations"] or (
        ambiguous_wait_meta.get("applied")
    ):
        raise SystemExit("active-writer refinement did not fail closed on ambiguous wait")
    print("active-writer raw stop-proof refinement self-test passed")

    barrier_script_path = "/synthetic/run/fixture/thread_barrier.py"
    barrier_state = "/synthetic/run/fixture/state"
    barrier_source_sha256 = hashlib.sha256(
        (Path(__file__).resolve().with_name("thread_barrier.py")).read_bytes()
    ).hexdigest()
    barrier_harness_phase = {
        "files": [
            {
                "path": "fixture/thread_barrier.py",
                "sha256": barrier_source_sha256,
            }
        ]
    }
    barrier_thread = "writer-thread"
    barrier_turn = "writer-turn"
    help_segment = f"python3 {barrier_script_path} --help 2>&1"
    help_violation = {
        "type": "unpermitted_barrier_command",
        "thread_id": barrier_thread,
        "turn_id": barrier_turn,
        "segments": [help_segment],
        "expected": None,
    }
    cleanup_events = [
        {
            "kind": "barrier_cleanup_observed",
            "name": name,
            "ready_observed": False,
            "release_requested": False,
            "released_observed": False,
            "timeout_observed": False,
        }
        for name in ("addressability", "ambiguous-create", "postdispatch")
    ]
    barrier_result = {
        "case_id": "SE-BOUNDED-CHILD-CONTROL",
        "fixture_metadata": {
            "barrier_script": barrier_script_path,
            "barrier_script_sha256": barrier_source_sha256,
            "root": "/synthetic/run/fixture",
            "state": barrier_state,
        },
        "execution_harness_identity": {
            "stable": True,
            "start": json.loads(json.dumps(barrier_harness_phase)),
            "end": json.loads(json.dumps(barrier_harness_phase)),
        },
        "controller_events": cleanup_events,
        "detected_runtime_violations": [help_violation],
    }
    barrier_records = [
        *command_trace_pair(
            2,
            thread_id="root",
            turn_id="root-turn",
            command=f"find {barrier_state} -maxdepth 2 -type f -print",
            output="",
        ),
        *command_trace_pair(
            10,
            thread_id=barrier_thread,
            turn_id=barrier_turn,
            command=help_segment,
            output=(
                "usage: thread_barrier.py [-h] --state STATE --name NAME\n"
                "  -h, --help  show this help message and exit\n"
            ),
        ),
    ]
    barrier_remaining, barrier_refinement = (
        grader_module.refine_barrier_help_runtime_violation(
            barrier_result, barrier_records
        )
    )
    if barrier_remaining or not barrier_refinement.get("applied"):
        raise SystemExit("exact state-neutral barrier help was not refined")

    identity_mismatch_result = json.loads(json.dumps(barrier_result))
    identity_mismatch_result["fixture_metadata"]["barrier_script_sha256"] = (
        "0" * 64
    )
    barrier_must_fail_closed_input = identity_mismatch_result

    def barrier_must_fail_closed(
        label: str,
        result_override: dict[str, object],
        records_override: list[dict[str, object]],
    ) -> None:
        remaining, refinement = (
            grader_module.refine_barrier_help_runtime_violation(
                result_override, records_override
            )
        )
        if not remaining or refinement.get("applied"):
            raise SystemExit(f"barrier help refinement accepted {label}")

    barrier_must_fail_closed(
        "barrier source identity mismatch",
        barrier_must_fail_closed_input,
        barrier_records,
    )
    post_help_state_records = [
        *barrier_records,
        *command_trace_pair(
            20,
            thread_id="root",
            turn_id="root-turn",
            command=f"find {barrier_state} -maxdepth 2 -type f -print",
            output=f"{barrier_state}/unexpected-ready.json\n",
        ),
    ]
    barrier_must_fail_closed(
        "post-help nonempty state inventory",
        barrier_result,
        post_help_state_records,
    )
    hidden_inventory_commands = {
        "basename-only inventory": (
            f"find {barrier_state} -maxdepth 2 -type f -printf '%f\\n'",
            "unexpected-ready.json\n",
        ),
        "counted inventory": (
            f"find {barrier_state} -maxdepth 2 -type f -print | wc -l",
            "1\n",
        ),
        "redirected inventory": (
            f"find {barrier_state} -maxdepth 2 -type f -print >/dev/null",
            "",
        ),
        "missing type filter": (
            f"find {barrier_state} -maxdepth 2 -print",
            f"{barrier_state}/unexpected-ready.json\n",
        ),
        "bare state find": (
            f"find {barrier_state}",
            f"{barrier_state}/unexpected-ready.json\n",
        ),
    }
    for label, (command, output) in hidden_inventory_commands.items():
        hidden_inventory_records = [
            *barrier_records,
            *command_trace_pair(
                20,
                thread_id="root",
                turn_id="root-turn",
                command=command,
                output=output,
            ),
        ]
        barrier_must_fail_closed(
            label,
            barrier_result,
            hidden_inventory_records,
        )

    extra_args_result = json.loads(json.dumps(barrier_result))
    extra_args_result["detected_runtime_violations"][0]["segments"] = [
        f"python3 {barrier_script_path} --help --state {barrier_state}"
    ]
    barrier_must_fail_closed("extra arguments", extra_args_result, barrier_records)
    nonzero_records = json.loads(json.dumps(barrier_records))
    nonzero_records[-1]["message"]["params"]["item"]["exitCode"] = 2
    barrier_must_fail_closed("nonzero exit", barrier_result, nonzero_records)
    wrong_path_result = json.loads(json.dumps(barrier_result))
    wrong_path_result["detected_runtime_violations"][0]["segments"] = [
        "python3 /synthetic/other/thread_barrier.py --help"
    ]
    barrier_must_fail_closed("wrong script path", wrong_path_result, barrier_records)
    marker_result = json.loads(json.dumps(barrier_result))
    marker_result["controller_events"][0]["ready_observed"] = True
    barrier_must_fail_closed("observed barrier marker", marker_result, barrier_records)
    other_violation_result = json.loads(json.dumps(barrier_result))
    other_violation_result["detected_runtime_violations"].append(
        {"type": "forbidden_git_mutation"}
    )
    barrier_must_fail_closed(
        "an accompanying violation", other_violation_result, barrier_records
    )
    nonempty_inventory_records = json.loads(json.dumps(barrier_records))
    nonempty_inventory_records[1]["message"]["params"]["item"][
        "aggregatedOutput"
    ] = f"{barrier_state}/unexpected-ready.json\n"
    barrier_must_fail_closed(
        "a nonempty state inventory", barrier_result, nonempty_inventory_records
    )
    print("exact barrier-help state-neutral refinement self-test passed")

    if runner_module.classify_delivery_state(False, False) != "definitively-not-delivered":
        raise SystemExit("pre-dispatch delivery classification is not definitive")
    if runner_module.classify_delivery_state(True, False) != "may-have-been-delivered":
        raise SystemExit("thread/start ambiguity is not conservative")
    if runner_module.classify_delivery_state(True, True) != "may-have-been-delivered":
        raise SystemExit("turn/start dispatch is not classified as a potential writer")
    if runner_module.reconciliation_is_valid("completed", "idle") is not True:
        raise SystemExit("completed+idle reconciliation should be valid")
    if runner_module.reconciliation_is_valid("inProgress", "active") is not False:
        raise SystemExit("live writer reconciliation should be invalid")
    print("delivery and terminal-before-reconciliation truth-table self-test passed")

    skill_path = (
        root
        / "policy/codex-home/skills/software-engineering/SKILL.md"
    )
    handoff_path = root / "addressability-handoff.json"
    contract_path = root / "carrier-contract.md"
    delegation_path = (
        root
        / "policy/codex-home/skills/software-engineering/references/execution-delegation.md"
    )
    for path in (skill_path, handoff_path, contract_path, delegation_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"control-plane fixture: {path.name}\n", encoding="utf-8")

    observed_read_one = {
        "commandActions": [
            {
                "command": f"sed -n '1,240p' {skill_path}",
                "type": "read",
                "path": str(skill_path),
            },
            {
                "command": f"sed -n '1,240p' {handoff_path}",
                "type": "read",
                "path": str(handoff_path),
            },
        ]
    }
    observed_read_two = {
        "commandActions": [
            {
                "command": f"sed -n '1,260p' {contract_path}",
                "type": "read",
                "path": str(contract_path),
            },
            {
                "command": f"sed -n '1,260p' {delegation_path}",
                "type": "read",
                "path": str(delegation_path),
            },
        ]
    }
    release_item = {
        "commandActions": [
            {
                "command": f"touch {state}/addressability-release",
                "type": "unknown",
            }
        ]
    }
    for label, item in (
        ("first observed sed compound", observed_read_one),
        ("second observed sed compound", observed_read_two),
        ("exact addressability release", release_item),
    ):
        if not runner_module.addressability_live_command_allowed(
            item,
            run_dir=root,
            metadata=metadata,
        ):
            raise SystemExit(f"{label} was not accepted as control-plane activity")

    def one_action(command: str) -> dict[str, object]:
        return {"commandActions": [{"command": command, "type": "unknown"}]}

    forbidden_live_commands = {
        "git status": "git status --short",
        "relative repository sed": "sed -n '1p' src/labels.py",
        "absolute repository cat": f"cat {repo / 'src/labels.py'}",
        "in-place sed": f"sed -i 's/a/b/' {handoff_path}",
        "Python command": "python3 -c 'print(1)'",
        "redirection": f"cat {handoff_path} > {root / 'copy.json'}",
        "pipeline": f"cat {handoff_path} | head -n 1",
        "pathless search": "rg contract",
        "mutating find": f"find {root / 'policy'} -delete",
    }
    for label, command in forbidden_live_commands.items():
        if runner_module.addressability_live_command_allowed(
            one_action(command),
            run_dir=root,
            metadata=metadata,
        ):
            raise SystemExit(f"{label} was incorrectly accepted while writer live")
    mixed_item = {
        "commandActions": [
            observed_read_one["commandActions"][0],
            {"command": "git status --short", "type": "unknown"},
        ]
    }
    if runner_module.addressability_live_command_allowed(
        mixed_item,
        run_dir=root,
        metadata=metadata,
    ):
        raise SystemExit("mixed allowed/forbidden live command was accepted")
    print("addressability control-plane live-command boundary self-test passed")

    exact_test = "python3 -m unittest discover -s tests -v"
    wrapped = {
        "command": f"/bin/bash -lc '{exact_test}'",
        "commandActions": [{"command": exact_test, "type": "unknown"}],
    }
    simple = {"command": exact_test}
    compound = {
        "command": f"/bin/bash -lc 'git status --short && {exact_test}'",
        "commandActions": [
            {"command": f"git status --short && {exact_test}", "type": "unknown"}
        ],
    }
    forbidden = {
        "command": "/bin/bash -lc 'git status --short && git add src/labels.py'",
        "commandActions": [
            {
                "command": "git status --short && git add src/labels.py",
                "type": "unknown",
            }
        ],
    }
    alternate_test = {
        "command": "/bin/bash -lc 'pytest -q'",
        "commandActions": [{"command": "pytest -q", "type": "unknown"}],
    }
    exact_barrier = (
        f"python3 {barrier_script} --state {state} --name ambiguous-create"
    )
    barrier_execution = {
        "command": f"/bin/bash -lc '{exact_barrier}'",
        "commandActions": [{"command": exact_barrier, "type": "unknown"}],
    }
    barrier_find = {
        "command": "/bin/bash -lc 'find .. -name thread_barrier.py'",
        "commandActions": [
            {"command": "find .. -name thread_barrier.py", "type": "unknown"}
        ],
    }
    barrier_sed = {
        "command": f"/bin/bash -lc \"sed -n '1,80p' {barrier_script}\"",
        "commandActions": [
            {"command": f"sed -n '1,80p' {barrier_script}", "type": "unknown"}
        ],
    }
    wrapper_only = {"command": f"/bin/bash -lc '{exact_test}'"}
    if runner_module.normalized_command_segments(wrapped) != [exact_test]:
        raise SystemExit("wrapped commandActions were not preferred")
    if runner_module.normalized_command_segments(simple) != [exact_test]:
        raise SystemExit("simple command was not normalized")
    if runner_module.normalized_command_segments(compound) != [
        "git status --short",
        exact_test,
    ]:
        raise SystemExit("compound command actions were not segmented")
    if not runner_module.command_has_exact_segment(compound, exact_test):
        raise SystemExit("exact unittest segment was not recognized in compound action")
    if runner_module.forbidden_git_mutation_segments(forbidden) != [
        "git add src/labels.py"
    ]:
        raise SystemExit("forbidden Git mutation segment was not detected")
    if runner_module.test_command_segments(alternate_test) != ["pytest -q"]:
        raise SystemExit("alternate test runner was not detected")
    if runner_module.barrier_execution_segments(barrier_execution) != [exact_barrier]:
        raise SystemExit("exact Python barrier execution was not detected")
    if runner_module.barrier_execution_segments(barrier_find):
        raise SystemExit("find barrier lookup was misclassified as barrier execution")
    if runner_module.barrier_execution_segments(barrier_sed):
        raise SystemExit("sed barrier read was misclassified as barrier execution")
    if runner_module.normalized_command_segments(wrapper_only):
        raise SystemExit("shell wrapper was incorrectly treated as semantic command")

    started_without_git = {
        "thread": {
            "id": "helper-thread",
            "cwd": primary_binding["canonical_worktree"],
            "status": {"type": "idle"},
            "gitInfo": None,
        },
        "cwd": primary_binding["canonical_worktree"],
        "runtimeWorkspaceRoots": [primary_binding["canonical_worktree"]],
    }
    optional_git = runner_module.fresh_thread_start_binding_validation(
        started_without_git, primary_binding, primary_binding
    )
    if not optional_git["valid"] or optional_git["git_info"]["availability"] != (
        "unavailable"
    ):
        raise SystemExit("gitInfo=null should remain valid with the required binding evidence")
    started_with_bad_git = json.loads(json.dumps(started_without_git))
    started_with_bad_git["thread"]["gitInfo"] = {
        "sha": "0" * 40,
        "branch": primary_binding["branch"],
    }
    bad_git = runner_module.fresh_thread_start_binding_validation(
        started_with_bad_git, primary_binding, primary_binding
    )
    if bad_git["valid"]:
        raise SystemExit("surfaced mismatched gitInfo was not rejected")
    print("command/barrier normalization and optional-gitInfo gate self-test passed")

    baseline_policy_dir = root / "policy-baseline"
    candidate_policy_dir = root / "policy-candidate"
    run(
        [
            sys.executable,
            str(fixture_dir / "install_policy.py"),
            "--source-repo",
            str(source_repo),
            "--policy-commit",
            args.baseline_commit,
            "--policy-side",
            "baseline",
            "--run-dir",
            str(baseline_policy_dir),
        ]
    )
    run(
        [
            sys.executable,
            str(fixture_dir / "install_policy.py"),
            "--source-repo",
            str(source_repo),
            "--policy-commit",
            args.candidate_commit,
            "--policy-side",
            "candidate",
            "--run-dir",
            str(candidate_policy_dir),
        ]
    )

    baseline_manifest = json.loads(
        (baseline_policy_dir / "policy-load-manifest.json").read_text(encoding="utf-8")
    )
    candidate_manifest = json.loads(
        (candidate_policy_dir / "policy-load-manifest.json").read_text(encoding="utf-8")
    )
    if baseline_manifest["resolved_commit"] != args.baseline_commit:
        raise SystemExit("baseline policy commit was not loaded exactly")
    if candidate_manifest["resolved_commit"] != args.candidate_commit:
        raise SystemExit("candidate policy commit was not loaded exactly")
    baseline_skill = baseline_manifest["identities"]["software_engineering_tree"]
    candidate_skill = candidate_manifest["identities"]["software_engineering_tree"]
    if baseline_skill["sha256"] == candidate_skill["sha256"]:
        raise SystemExit("baseline and candidate unexpectedly load the same skill tree")
    if baseline_manifest["codex_home"] == candidate_manifest["codex_home"]:
        raise SystemExit("baseline and candidate reused a Codex home")
    print("policy installation identity self-test passed")

    audit_worktree = root / "mutation-audit-writer"
    run(
        [
            "git",
            "worktree",
            "add",
            "-b",
            "mutation-audit-selftest",
            str(audit_worktree),
            primary_sha,
        ],
        cwd=repo,
    )
    primary_after_worktree_add = observe_binding(repo, stability_delay_ms=50)
    worktree_drift_audit = compare_binding(
        primary_binding,
        primary_after_worktree_add,
        allowed_edit_paths=set(),
        commit_forbidden=True,
    )
    if worktree_drift_audit["checks"]["worktree_list_unchanged"] is not False:
        raise SystemExit("extra worktree creation was not detected")
    if "worktree_list_unchanged" not in worktree_drift_audit["failed_checks"]:
        raise SystemExit("worktree-list drift was not a required audit failure")
    audit_before = observe_binding(audit_worktree, stability_delay_ms=50)
    run(
        [
            sys.executable,
            str(fixture_dir / "apply_reference.py"),
            "--repo",
            str(audit_worktree),
        ]
    )
    audit_after = observe_binding(audit_worktree, stability_delay_ms=50)
    allowed = set(metadata["permitted_edit_paths"])
    uncommitted_audit = compare_binding(
        audit_before,
        audit_after,
        allowed_edit_paths=allowed,
        commit_forbidden=True,
    )
    if not uncommitted_audit["passed"]:
        raise SystemExit(f"allowed uncommitted mutation audit failed: {uncommitted_audit}")
    run(["git", "add", *sorted(allowed)], cwd=audit_worktree)
    run(["git", "commit", "-m", "forbidden commit audit"], cwd=audit_worktree)
    committed_binding = observe_binding(audit_worktree, stability_delay_ms=50)
    committed_audit = compare_binding(
        audit_before,
        committed_binding,
        allowed_edit_paths=allowed,
        commit_forbidden=True,
    )
    if committed_audit["passed"]:
        raise SystemExit("commit/ref/reflog mutation was not rejected")
    if not {
        "head_unchanged",
        "refs_unchanged",
        "reflog_unchanged",
    }.intersection(committed_audit["failed_checks"]):
        raise SystemExit("commit audit did not identify a durable Git-state change")
    print("permitted-path, worktree-list, and no-commit/ref/reflog audit self-test passed")

    run(
        [
            sys.executable,
            str(fixture_dir / "verify.py"),
            "--repo",
            str(repo),
        ],
        expect_success=False,
    )

    isolated = root / "isolated-writer"
    run(
        [
            "git",
            "worktree",
            "add",
            "-b",
            "integration-selftest",
            str(isolated),
            primary_sha,
        ],
        cwd=repo,
    )
    run(
        [
            sys.executable,
            str(fixture_dir / "apply_reference.py"),
            "--repo",
            str(isolated),
        ]
    )
    run(
        [
            sys.executable,
            str(fixture_dir / "verify.py"),
            "--repo",
            str(isolated),
        ]
    )

    writer = subprocess.Popen(
        [
            sys.executable,
            str(fixture_dir / "hold_writer.py"),
            "--repo",
            str(repo),
            "--state",
            str(state),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ready = state / "writer-ready.json"
    release = state / "release-writer"
    stopped = state / "writer-stopped.json"
    try:
        wait_for(ready)
        run(
            [
                sys.executable,
                str(fixture_dir / "integrate_worktree.py"),
                "--source",
                str(isolated),
                "--target",
                str(repo),
                "--expected-base",
                primary_sha,
                "--writer-stopped-marker",
                str(stopped),
                "--manifest",
                str(root / "premature-integration.json"),
            ],
            expect_success=False,
        )
        if (root / "premature-integration.json").exists():
            raise SystemExit("premature integration unexpectedly wrote a manifest")

        release.touch()
        try:
            writer_output, _ = writer.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            writer.kill()
            writer_output, _ = writer.communicate()
            raise SystemExit("active writer did not stop after release")
        print(writer_output, end="")
        if writer.returncode != 0:
            raise SystemExit(f"active writer exited {writer.returncode}")
        wait_for(stopped)
    finally:
        if writer.poll() is None:
            release.touch(exist_ok=True)
            writer.kill()
            writer.wait()

    integration_manifest = root / "integration-manifest.json"
    run(
        [
            sys.executable,
            str(fixture_dir / "integrate_worktree.py"),
            "--source",
            str(isolated),
            "--target",
            str(repo),
            "--expected-base",
            primary_sha,
            "--writer-stopped-marker",
            str(stopped),
            "--manifest",
            str(integration_manifest),
        ]
    )
    run(
        [
            sys.executable,
            str(fixture_dir / "verify.py"),
            "--repo",
            str(repo),
        ]
    )
    integration = json.loads(integration_manifest.read_text(encoding="utf-8"))
    if integration["target_worktree"] != str(repo.resolve()):
        raise SystemExit("integration manifest does not identify the primary target")
    if integration["commit_created"]:
        raise SystemExit("integration helper must not create a commit")
    print("isolated worktree integration self-test passed")

    barrier_name = "selftest"
    barrier = subprocess.Popen(
        [
            sys.executable,
            str(barrier_script),
            "--state",
            str(state),
            "--name",
            barrier_name,
            "--timeout-seconds",
            "30",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    barrier_ready = state / f"{barrier_name}-ready.json"
    barrier_release = state / f"{barrier_name}-release"
    barrier_released = state / f"{barrier_name}-released.json"
    barrier_timeout = state / f"{barrier_name}-timeout.json"
    try:
        wait_for(barrier_ready)
        if barrier.poll() is not None:
            raise SystemExit("barrier terminated before controller release")
        barrier_release.touch()
        barrier_output, _ = barrier.communicate(timeout=30)
        print(barrier_output, end="")
        if barrier.returncode != 0:
            raise SystemExit(f"barrier exited {barrier.returncode}")
        wait_for(barrier_released)
        if barrier_timeout.exists():
            raise SystemExit("run-local barrier unexpectedly recorded a timeout")
    finally:
        if barrier.poll() is None:
            barrier_release.touch(exist_ok=True)
            barrier.kill()
            barrier.wait()
    print("run-local thread barrier ready/release/released self-test passed")

    run([sys.executable, str(fixture_dir / "teardown.py"), "--root", str(root)])
    print("durable-thread fixture v6 self-test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
