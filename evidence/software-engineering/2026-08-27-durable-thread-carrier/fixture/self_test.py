#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import evidence_contract
from inspect_binding import compare_binding
from inspect_binding import observe_binding
import publish_evidence


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    expect_success: bool = True,
    show_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(args), flush=True)
    completed = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if show_output:
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
    grading_identity = evidence_contract.compute_grading_harness_identity()
    complete_manifest = {
        "schema_version": 6,
        "evaluation_id": grader_module.EVALUATION_ID,
        "artifact_scope": evidence_contract.ARTIFACT_SCOPE,
        "baseline_commit": grader_module.BASELINE_COMMIT,
        "candidate_commit": grader_module.CANDIDATE_COMMIT,
        "execution_harness_sha256": harness_identity[
            "execution_harness_sha256"
        ],
        "grading_harness_sha256": grading_identity[
            "grading_harness_sha256"
        ],
        "primary_run_policy": evidence_contract.PRIMARY_RUN_POLICY,
        "runs": manifest_runs,
    }
    if grader_module.validate_manifest(complete_manifest):
        raise SystemExit("grader rejected a complete identity-bound manifest")
    missing_execution_identity = json.loads(json.dumps(complete_manifest))
    del missing_execution_identity["execution_harness_sha256"]
    if not grader_module.validate_manifest(missing_execution_identity):
        raise SystemExit("grader accepted a manifest without harness identity")
    missing_grading_identity = json.loads(json.dumps(complete_manifest))
    del missing_grading_identity["grading_harness_sha256"]
    if not grader_module.validate_manifest(missing_grading_identity):
        raise SystemExit("grader accepted a manifest without grading identity")
    mismatched_grading_identity = json.loads(json.dumps(complete_manifest))
    mismatched_grading_identity["grading_harness_sha256"] = "0" * 64
    if not grader_module.validate_manifest(mismatched_grading_identity):
        raise SystemExit("grader accepted a mismatched grading identity")
    null_grading_identity = json.loads(json.dumps(complete_manifest))
    null_grading_identity["grading_harness_sha256"] = None
    if not grader_module.validate_manifest(null_grading_identity):
        raise SystemExit("grader accepted a null grading identity")
    print("tracked execution/grading identity manifest gates self-test passed")

    if evidence_contract.grading_harness_identity_errors(grading_identity):
        raise SystemExit("shared grading-harness identity is invalid")
    if tuple(item["path"] for item in grading_identity["files"]) != (
        "evidence_contract.py",
        "grade_runs.py",
        "publish_evidence.py",
    ):
        raise SystemExit("grading-harness identity inventory is incomplete")
    tampered_grading_identity = json.loads(json.dumps(grading_identity))
    tampered_grading_identity["files"][0]["size_bytes"] += 1
    if not evidence_contract.grading_harness_identity_errors(
        tampered_grading_identity
    ):
        raise SystemExit("grading-harness identity tampering was not detected")
    for payload in (
        b'{"apiKey":"x","apiKey":""}',
        b'{"number":NaN}',
        b'{"number":Infinity}',
        b'{"number":-Infinity}',
    ):
        try:
            evidence_contract.strict_json_loads(
                payload, description="strict JSON self-test"
            )
        except evidence_contract.PublicationError:
            pass
        else:
            raise SystemExit("strict JSON parser accepted ambiguous input")
    print(
        "shared grading-harness identity and strict JSON coverage self-test passed"
    )

    invalid_manifest_path = root / "invalid-grader-manifest.json"
    invalid_manifest_path.write_text(
        json.dumps(missing_execution_identity, sort_keys=True), encoding="utf-8"
    )
    invalid_grade = run(
        [
            sys.executable,
            str(grader_path),
            "--manifest",
            str(invalid_manifest_path),
        ],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    try:
        invalid_grade_report = json.loads(invalid_grade.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("nonzero grader did not emit a complete JSON report") from exc
    if invalid_grade_report.get("summary", {}).get("exit_status") != 1 or not (
        invalid_grade_report.get("manifest_errors")
    ):
        raise SystemExit("invalid grader report did not explain its nonzero exit")
    if not invalid_grade_report.get("grading_harness_identity"):
        raise SystemExit("grader report omitted the grading-harness identity")
    for grade in ("fail", "invalid-or-unsupported"):
        if not grader_module.report_requires_nonzero_exit(
            {
                "manifest_errors": [],
                "runs": [{"side": "candidate", "grade": grade}],
            }
        ):
            raise SystemExit(f"grader exit gate accepted candidate {grade}")
    frozen_invalid = grader_module.EXPECTED_FROZEN_INVALID_RUNS[
        ("baseline", "SE-DURABLE-ADDRESSABILITY-RESUME")
    ]
    frozen_invalid_item = {
        "case_id": "SE-DURABLE-ADDRESSABILITY-RESUME",
        "side": "baseline",
        "grade": "invalid-or-unsupported",
        **{
            field: frozen_invalid[field]
            for field in (
                "run_id",
                "replicate",
                "result_sha256",
                "raw_trace_sha256",
            )
        },
        "invalid_reasons": sorted(frozen_invalid["invalid_reasons"]),
    }
    exact_frozen_report = {
        "manifest_errors": [],
        "runs": [frozen_invalid_item],
    }
    if grader_module.report_requires_nonzero_exit(exact_frozen_report):
        raise SystemExit("grader exit gate rejected the exact frozen invalid run")
    for field, replacement in (
        ("run_id", "b-other-run"),
        ("replicate", "replacement"),
        ("result_sha256", "0" * 64),
        ("raw_trace_sha256", "1" * 64),
    ):
        mutated_report = json.loads(json.dumps(exact_frozen_report))
        mutated_report["runs"][0][field] = replacement
        if not grader_module.report_requires_nonzero_exit(mutated_report):
            raise SystemExit(
                f"grader exit gate accepted frozen-invalid {field} substitution"
            )
    print(
        "grader complete-JSON and exact frozen-invalid identity gate self-test passed"
    )

    publication_root = root / "publication-sources"
    publication_root.mkdir()
    publication_bytes: dict[str, bytes] = {}

    def artifact_payload(relative: str, index: int) -> bytes:
        if relative.endswith(".json"):
            return (json.dumps({"artifact": relative}, sort_keys=True) + "\n").encode()
        if relative.endswith(".jsonl"):
            return (json.dumps({"artifact": relative}, sort_keys=True) + "\n").encode()
        return f"allowlisted artifact {index}: {relative}\n".encode()

    def write_publish_manifest(run_dir: Path) -> dict[str, object]:
        entries: list[dict[str, object]] = []
        for index, relative in enumerate(
            sorted(evidence_contract.REQUIRED_PUBLISH_PATHS)
        ):
            payload = artifact_payload(relative, index)
            path = run_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            publication_bytes.setdefault(relative, payload)
            entries.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                }
            )
        publish = {
            "schema_version": 1,
            "publication_mode": "explicit allowlist only",
            "compatibility_surface": evidence_contract.PUBLISH_COMPATIBILITY_SURFACE,
            "explicitly_excluded": evidence_contract.PUBLISH_EXPLICITLY_EXCLUDED,
            "files": entries,
        }
        (run_dir / "publish-manifest.json").write_text(
            json.dumps(publish, sort_keys=True), encoding="utf-8"
        )
        return publish

    synthetic_runs: list[dict[str, object]] = []
    source_publish_manifests: list[dict[str, object]] = []
    for index, (case_id, side) in enumerate(
        (case, side)
        for case in evidence_contract.CASE_IDS
        for side in ("baseline", "candidate")
    ):
        run_id = f"synthetic-{index:02d}-{side}"
        run_dir = publication_root / run_id
        run_dir.mkdir()
        publish = write_publish_manifest(run_dir)
        source_publish_manifests.append(publish)
        by_path = {entry["path"]: entry for entry in publish["files"]}
        synthetic_runs.append(
            {
                "case_id": case_id,
                "side": side,
                "replicate": "primary",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "result_sha256": by_path["result.json"]["sha256"],
                "raw_trace_sha256": by_path["raw-trace.jsonl"]["sha256"],
            }
        )
    synthetic_behavior_manifest = {
        "schema_version": 6,
        "evaluation_id": evidence_contract.EVALUATION_ID,
        "artifact_scope": evidence_contract.ARTIFACT_SCOPE,
        "baseline_commit": evidence_contract.BASELINE_COMMIT,
        "candidate_commit": evidence_contract.CANDIDATE_COMMIT,
        "execution_harness_sha256": evidence_contract.EXECUTION_HARNESS_SHA256,
        "grading_harness_sha256": grading_identity[
            "grading_harness_sha256"
        ],
        "primary_run_policy": evidence_contract.PRIMARY_RUN_POLICY,
        "runs": synthetic_runs,
    }
    synthetic_manifest_path = root / "synthetic-behavior-manifest.json"

    def write_behavior_manifest() -> None:
        synthetic_manifest_path.write_text(
            json.dumps(synthetic_behavior_manifest, sort_keys=True),
            encoding="utf-8",
        )

    def refresh_artifact(index: int, relative: str, payload: bytes) -> None:
        run_dir = Path(str(synthetic_runs[index]["run_dir"]))
        (run_dir / relative).write_bytes(payload)
        publish = source_publish_manifests[index]
        entry = next(item for item in publish["files"] if item["path"] == relative)
        entry["sha256"] = hashlib.sha256(payload).hexdigest()
        entry["size_bytes"] = len(payload)
        (run_dir / "publish-manifest.json").write_text(
            json.dumps(publish, sort_keys=True), encoding="utf-8"
        )
        if relative == "result.json":
            synthetic_runs[index]["result_sha256"] = entry["sha256"]
        elif relative == "raw-trace.jsonl":
            synthetic_runs[index]["raw_trace_sha256"] = entry["sha256"]
        write_behavior_manifest()

    write_behavior_manifest()
    secret = Path(str(synthetic_runs[0]["run_dir"])) / "policy/codex-home/auth.json"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("must-not-publish\n", encoding="utf-8")

    legacy_behavior_manifest = json.loads(json.dumps(synthetic_behavior_manifest))
    del legacy_behavior_manifest["grading_harness_sha256"]
    legacy_manifest_path = root / "legacy-unbound-behavior-manifest.json"
    legacy_manifest_path.write_text(
        json.dumps(legacy_behavior_manifest, sort_keys=True), encoding="utf-8"
    )
    bound_manifest_path = root / "identity-bound-behavior-manifest.json"
    bind_result = run(
        [
            sys.executable,
            str(fixture_dir / "publish_evidence.py"),
            "--manifest",
            str(legacy_manifest_path),
            "--bind-output",
            str(bound_manifest_path),
        ],
        cwd=source_repo,
        show_output=False,
    )
    bind_report = json.loads(bind_result.stdout)
    bound_behavior_manifest = evidence_contract.read_path_json_no_symlink(
        bound_manifest_path,
        max_bytes=evidence_contract.MAX_BEHAVIOR_MANIFEST_BYTES,
    )
    if (
        not bind_report.get("bound")
        or bound_behavior_manifest.get("grading_harness_sha256")
        != grading_identity["grading_harness_sha256"]
        or any(
            not Path(entry["run_dir"]).is_absolute()
            for entry in bound_behavior_manifest["runs"]
        )
        or grader_module.validate_manifest(bound_behavior_manifest)
    ):
        raise SystemExit("manifest binder did not produce a current portable manifest")
    bound_grade = run(
        [sys.executable, str(grader_path), "--manifest", str(bound_manifest_path)],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    bound_grade_report = json.loads(bound_grade.stdout)
    if len(bound_grade_report.get("runs", [])) != 20 or any(
        "grading_harness_sha256" in reason
        for reason in bound_grade_report.get("manifest_errors", [])
    ):
        raise SystemExit("identity-bound manifest was not evaluated by the grader")
    unbound_grade = run(
        [sys.executable, str(grader_path), "--manifest", str(legacy_manifest_path)],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    unbound_grade_report = json.loads(unbound_grade.stdout)
    if not any(
        "grading_harness_sha256" in reason
        for reason in unbound_grade_report.get("manifest_errors", [])
    ):
        raise SystemExit("grader accepted a legacy manifest without grading binding")
    mismatched_manifest = json.loads(json.dumps(bound_behavior_manifest))
    mismatched_manifest["grading_harness_sha256"] = "0" * 64
    mismatched_manifest_path = root / "mismatched-grading-manifest.json"
    mismatched_manifest_path.write_text(
        json.dumps(mismatched_manifest, sort_keys=True), encoding="utf-8"
    )
    mismatched_grade = run(
        [
            sys.executable,
            str(grader_path),
            "--manifest",
            str(mismatched_manifest_path),
        ],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    mismatched_grade_report = json.loads(mismatched_grade.stdout)
    if not any(
        "grading_harness_sha256 mismatch" in reason
        for reason in mismatched_grade_report.get("manifest_errors", [])
    ):
        raise SystemExit("grader accepted a mismatched grading binding")
    print("grading-harness manifest bind/missing/mismatch self-test passed")

    malformed_result = {
        "case_id": synthetic_runs[0]["case_id"],
        "policy_side": synthetic_runs[0]["side"],
        "schema_version": 6,
        "boot": [],
    }
    original_result = publication_bytes["result.json"]
    refresh_artifact(
        0,
        "result.json",
        (json.dumps(malformed_result, sort_keys=True) + "\n").encode(),
    )
    malformed_result_grade = run(
        [sys.executable, str(grader_path), "--manifest", str(synthetic_manifest_path)],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    malformed_result_report = json.loads(malformed_result_grade.stdout)
    if malformed_result_report.get("summary", {}).get("exit_status") != 1:
        raise SystemExit("malformed nested result did not produce complete nonzero JSON")
    refresh_artifact(0, "result.json", original_result)

    malformed_manifest = json.loads(json.dumps(synthetic_behavior_manifest))
    malformed_manifest["runs"][0]["case_id"] = {"nested": "object"}
    malformed_manifest["runs"][1]["side"] = ["nested", "array"]
    malformed_manifest_path = root / "malformed-nested-manifest.json"
    malformed_manifest_path.write_text(
        json.dumps(malformed_manifest, sort_keys=True), encoding="utf-8"
    )
    malformed_manifest_grade = run(
        [sys.executable, str(grader_path), "--manifest", str(malformed_manifest_path)],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    malformed_manifest_report = json.loads(malformed_manifest_grade.stdout)
    if malformed_manifest_report.get("summary", {}).get("exit_status") != 1:
        raise SystemExit("malformed nested manifest did not produce complete nonzero JSON")

    canonical_manifest_text = json.dumps(
        synthetic_behavior_manifest, sort_keys=True
    )
    ambiguous_manifest_payloads = (
        '{"schema_version":6,' + canonical_manifest_text[1:],
        canonical_manifest_text.replace(
            '"schema_version": 6', '"schema_version": NaN', 1
        ),
    )
    for counter, payload in enumerate(ambiguous_manifest_payloads):
        ambiguous_manifest_path = root / f"ambiguous-manifest-{counter}.json"
        ambiguous_manifest_path.write_text(payload, encoding="utf-8")
        ambiguous_grade = run(
            [
                sys.executable,
                str(grader_path),
                "--manifest",
                str(ambiguous_manifest_path),
            ],
            cwd=source_repo,
            expect_success=False,
            show_output=False,
        )
        ambiguous_report = json.loads(ambiguous_grade.stdout)
        if (
            ambiguous_report.get("summary", {}).get("exit_status") != 1
            or not ambiguous_report.get("manifest_errors")
        ):
            raise SystemExit("ambiguous manifest did not produce complete nonzero JSON")

    missing_run_manifest = json.loads(json.dumps(synthetic_behavior_manifest))
    missing_run_manifest["runs"][0]["run_dir"] = str(root / "missing-run")
    missing_run_manifest_path = root / "missing-run-manifest.json"
    missing_run_manifest_path.write_text(
        json.dumps(missing_run_manifest, sort_keys=True), encoding="utf-8"
    )
    missing_run_grade = run(
        [sys.executable, str(grader_path), "--manifest", str(missing_run_manifest_path)],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    missing_run_report = json.loads(missing_run_grade.stdout)
    if (
        missing_run_report.get("summary", {}).get("exit_status") != 1
        or not missing_run_report.get("runs")
    ):
        raise SystemExit("missing run did not produce complete nonzero JSON")
    print("malformed manifest/result and missing-run subprocess self-test passed")

    publication_one = root / "published-one"
    publication_two = root / "published-two"
    first_publication = publish_evidence.publish_behavior_manifest(
        synthetic_manifest_path, publication_one
    )
    second_publication = publish_evidence.publish_behavior_manifest(
        legacy_manifest_path, publication_two
    )
    first_files = {
        path.relative_to(publication_one).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in publication_one.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(publication_two).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in publication_two.rglob("*")
        if path.is_file()
    }
    if first_files != second_files or first_publication["files"] != len(first_files):
        raise SystemExit("gzip publication is not byte-deterministic")

    mutation_output = root / "late-staging-mutation-output"
    original_final_verifier = publish_evidence._verify_staged_artifacts
    mutation_applied = False

    def mutate_before_final_staged_verification(
        staging_root: evidence_contract.ArtifactRoot,
        expectations: dict[str, dict[str, object]],
    ) -> None:
        nonlocal mutation_applied
        storage_path = next(
            path for path in sorted(expectations) if path.endswith(".gz")
        )
        parts = storage_path.split("/")
        directory_fd = os.dup(staging_root.fd)
        try:
            for part in parts[:-1]:
                next_fd = os.open(
                    part,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                os.close(directory_fd)
                directory_fd = next_fd
            artifact_fd = os.open(
                parts[-1],
                os.O_WRONLY | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            try:
                os.write(artifact_fd, b"X")
                os.fsync(artifact_fd)
            finally:
                os.close(artifact_fd)
        finally:
            os.close(directory_fd)
        mutation_applied = True
        original_final_verifier(staging_root, expectations)

    publish_evidence._verify_staged_artifacts = (
        mutate_before_final_staged_verification
    )
    try:
        try:
            publish_evidence.publish_behavior_manifest(
                synthetic_manifest_path, mutation_output
            )
        except evidence_contract.PublicationError as exc:
            if "final staged artifact verification failed" not in str(exc):
                raise SystemExit(
                    "publisher rejected late staging mutation for the wrong reason"
                )
        else:
            raise SystemExit("publisher accepted a late staged-gzip mutation")
    finally:
        publish_evidence._verify_staged_artifacts = original_final_verifier
    if (
        not mutation_applied
        or mutation_output.exists()
        or list(root.glob(f".{mutation_output.name}.staging-*"))
    ):
        raise SystemExit("late staging mutation did not fail cleanly")

    published_run = publication_one / f"runs/00-{synthetic_runs[0]['run_id']}"
    for relative, expected_bytes in publication_bytes.items():
        if evidence_contract.read_artifact_bytes(published_run, relative) != expected_bytes:
            raise SystemExit(f"compressed artifact roundtrip failed: {relative}")
        if (published_run / relative).exists() or not (
            published_run / f"{relative}.gz"
        ).is_file():
            raise SystemExit(f"published artifact form is not gzip-only: {relative}")
    if any("auth.json" in path for path in first_files):
        raise SystemExit("publisher copied non-allowlisted auth material")
    published_behavior = json.loads(
        (publication_one / "behavior-run-manifest.json").read_text(encoding="utf-8")
    )
    if published_behavior["runs"][0]["run_dir"] != (
        f"runs/00-{synthetic_runs[0]['run_id']}"
    ):
        raise SystemExit("published behavior manifest did not use a relative run path")
    published_grade = run(
        [
            sys.executable,
            str(grader_path),
            "--manifest",
            str(publication_one / "behavior-run-manifest.json"),
        ],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    published_grade_report = json.loads(published_grade.stdout)
    if (
        published_grade_report.get("summary", {}).get("exit_status") != 1
        or len(published_grade_report.get("runs", [])) != 20
    ):
        raise SystemExit("published evidence was not clone-regradable by the grader")

    for unsafe_path in ("/absolute/result.json", "../result.json", "a/../result.json"):
        try:
            evidence_contract.canonical_relative_path(unsafe_path)
        except evidence_contract.PublicationError:
            pass
        else:
            raise SystemExit(f"publisher accepted unsafe path: {unsafe_path}")
    publication_source = Path(str(synthetic_runs[0]["run_dir"]))
    publication_manifest = source_publish_manifests[0]
    duplicate_manifest = json.loads(json.dumps(publication_manifest))
    duplicate_manifest["files"].append(duplicate_manifest["files"][0])
    if not any(
        "duplicated" in reason
        for reason in evidence_contract.publication_invalid_reasons(
            publication_source,
            duplicate_manifest,
            "SE-BOUNDED-CHILD-CONTROL",
        )
    ):
        raise SystemExit("publisher accepted a duplicate publication path")
    non_allowlisted_manifest = json.loads(json.dumps(publication_manifest))
    payload = b"not allowed\n"
    (publication_source / "not-allowlisted.txt").write_bytes(payload)
    non_allowlisted_manifest["files"].append(
        {
            "path": "not-allowlisted.txt",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
    )
    if not any(
        "not allowlisted" in reason
        for reason in evidence_contract.publication_invalid_reasons(
            publication_source,
            non_allowlisted_manifest,
            "SE-BOUNDED-CHILD-CONTROL",
        )
    ):
        raise SystemExit("publisher accepted a non-allowlisted publication path")
    hash_mismatch_manifest = json.loads(json.dumps(publication_manifest))
    hash_mismatch_manifest["files"][0]["sha256"] = "0" * 64
    if not any(
        "hash mismatch" in reason
        for reason in evidence_contract.publication_invalid_reasons(
            publication_source,
            hash_mismatch_manifest,
            "SE-BOUNDED-CHILD-CONTROL",
        )
    ):
        raise SystemExit("publisher accepted an artifact hash mismatch")
    symlink_root = root / "publication-symlink"
    symlink_root.mkdir()
    (symlink_root / "target").write_text("target\n", encoding="utf-8")
    (symlink_root / "result.json").symlink_to(symlink_root / "target")
    try:
        opened = evidence_contract.open_artifact_fd(symlink_root, "result.json")
    except evidence_contract.PublicationError:
        pass
    else:
        os.close(opened.fd)
        raise SystemExit("publisher accepted a symlink artifact")
    missing_path = publication_source / publication_manifest["files"][0]["path"]
    missing_payload = missing_path.read_bytes()
    missing_path.unlink()
    missing_reasons = evidence_contract.publication_invalid_reasons(
        publication_source,
        publication_manifest,
        "SE-BOUNDED-CHILD-CONTROL",
    )
    missing_path.write_bytes(missing_payload)
    if not any("missing" in reason for reason in missing_reasons):
        raise SystemExit("publisher accepted a missing allowlisted artifact")

    existing_files_before = dict(first_files)
    try:
        publish_evidence.publish_behavior_manifest(
            synthetic_manifest_path, publication_one
        )
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("publisher replaced an existing destination")
    existing_files_after = {
        path.relative_to(publication_one).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in publication_one.rglob("*")
        if path.is_file()
    }
    if existing_files_before != existing_files_after:
        raise SystemExit("failed publication changed an existing destination")

    alias_manifest = json.loads(json.dumps(synthetic_behavior_manifest))
    alias_manifest["runs"][1]["run_dir"] = (
        str(synthetic_runs[0]["run_dir"]) + "/."
    )
    alias_manifest_path = root / "alias-behavior-manifest.json"
    alias_manifest_path.write_text(
        json.dumps(alias_manifest, sort_keys=True), encoding="utf-8"
    )
    alias_output = root / "alias-output"
    try:
        publish_evidence.publish_behavior_manifest(alias_manifest_path, alias_output)
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("publisher accepted a reused source directory inode")
    if alias_output.exists():
        raise SystemExit("failed alias publication left a partial output")

    incomplete_behavior = json.loads(json.dumps(synthetic_behavior_manifest))
    incomplete_behavior["runs"].pop()
    incomplete_behavior_path = root / "incomplete-behavior-manifest.json"
    incomplete_behavior_path.write_text(
        json.dumps(incomplete_behavior, sort_keys=True), encoding="utf-8"
    )
    try:
        publish_evidence.publish_behavior_manifest(
            incomplete_behavior_path, root / "incomplete-behavior-output"
        )
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("publisher accepted an incomplete behavior inventory")

    broken_linkage = json.loads(json.dumps(synthetic_behavior_manifest))
    broken_linkage["runs"][0]["result_sha256"] = "0" * 64
    broken_linkage_path = root / "broken-linkage-manifest.json"
    broken_linkage_path.write_text(
        json.dumps(broken_linkage, sort_keys=True), encoding="utf-8"
    )
    try:
        publish_evidence.publish_behavior_manifest(
            broken_linkage_path, root / "broken-linkage-output"
        )
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("publisher accepted behavior/publication hash mismatch")

    omitted_entry = source_publish_manifests[0]["files"].pop()
    (publication_source / "publish-manifest.json").write_text(
        json.dumps(source_publish_manifests[0], sort_keys=True), encoding="utf-8"
    )
    try:
        publish_evidence.publish_behavior_manifest(
            synthetic_manifest_path, root / "incomplete-publish-output"
        )
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("publisher accepted an incomplete per-run allowlist")
    source_publish_manifests[0]["files"].append(omitted_entry)
    source_publish_manifests[0]["files"].sort(key=lambda item: item["path"])
    (publication_source / "publish-manifest.json").write_text(
        json.dumps(source_publish_manifests[0], sort_keys=True), encoding="utf-8"
    )

    output_target = root / "symbolic-output-target"
    output_target.mkdir()
    output_link = root / "symbolic-output"
    output_link.symlink_to(output_target, target_is_directory=True)
    try:
        publish_evidence.publish_behavior_manifest(
            synthetic_manifest_path, output_link
        )
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("publisher accepted a symbolic output destination")
    if list(output_target.iterdir()):
        raise SystemExit("symbolic output rejection changed its target")

    source_symlink = root / "source-run-link"
    source_symlink.symlink_to(publication_source, target_is_directory=True)
    symlink_behavior = json.loads(json.dumps(synthetic_behavior_manifest))
    symlink_behavior["runs"][0]["run_dir"] = str(source_symlink)
    symlink_behavior_path = root / "symlink-behavior-manifest.json"
    symlink_behavior_path.write_text(
        json.dumps(symlink_behavior, sort_keys=True), encoding="utf-8"
    )
    try:
        publish_evidence.publish_behavior_manifest(
            symlink_behavior_path, root / "symlink-output"
        )
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("publisher accepted a symbolic source run root")

    mutation_path = publication_source / "carrier-contract.md"
    original_mutation_payload = mutation_path.read_bytes()
    try:
        with evidence_contract.open_artifact_root(publication_source) as source_root:
            with evidence_contract.open_artifact_binary(
                source_root, "carrier-contract.md"
            ) as source_stream:
                source_stream.read(1)
                mutation_path.write_bytes(original_mutation_payload + b"changed\n")
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("stable source-fd reader accepted concurrent mutation")
    mutation_path.write_bytes(original_mutation_payload)

    for sensitive_key in (
        "accessToken",
        "access_token",
        "access-token",
        "accesstoken",
        "apiKey",
        "clientSecret",
        "privateKey",
        "refreshToken",
        "secretAccessKey",
    ):
        if not evidence_contract.structured_credential_present(
            {sensitive_key: "x"}
        ):
            raise SystemExit(f"structured scan missed sensitive key: {sensitive_key}")
    for decoded_secret in (
        'password: "secret"',
        'Authorization: Basic "dXNlcjpw"',
        'Authorization: Bearer "x"',
        'X-API-Key: "x"',
    ):
        if not evidence_contract.structured_credential_present(
            {"output": decoded_secret}
        ):
            raise SystemExit("structured scan missed a decoded-string credential")
    harmless_credential_documentation = (
        b"This document discusses password, passphrase, and Authorization headers.\n"
        b"password\npassphrase:\nAuthorization: Basic\nAPI-Key:\n"
    )
    if evidence_contract.credential_pattern_present(
        harmless_credential_documentation
    ):
        raise SystemExit("text credential scan rejected value-free documentation")
    credential_cases = [
        ("result.json", b'{"accessToken":"x"}\n'),
        ("raw-trace.jsonl", b'{"apiKey":"x"}\n'),
        ("binding-observations.json", b'{"clientSecret":"x"}\n'),
        ("controller-events.jsonl", b'{"privateKey":"x"}\n'),
        ("reconciliation.json", b'{"refreshToken":"x"}\n'),
        ("mutation-audit.json", b'{"secretAccessKey":"x"}\n'),
        ("result.json", b'{"output":"password: \\"secret\\""}\n'),
        (
            "raw-trace.jsonl",
            b'{"output":"Authorization: Basic \\"dXNlcjpw\\""}\n',
        ),
        (
            "binding-observations.json",
            b'{"output":"Authorization: Bearer \\"x\\""}\n',
        ),
        ("controller-events.jsonl", b'{"output":"X-API-Key: \\"x\\""}\n'),
        ("result.json", b'{"apiKey":"x","apiKey":""}\n'),
        ("initial-primary-binding.json", b'{"number":NaN}\n'),
        ("controller-events.jsonl", b'{"number":Infinity}\n'),
        ("carrier-contract.md", b"password: short-secret\n"),
        ("final-git-status.txt", b"passphrase = 'x'\n"),
        ("final-git-status.txt", b"db_password=x\n"),
        ("oracle.log", b"db-password: x\n"),
        ("carrier-contract.md", b"pass_phrase=x\n"),
        ("final-diff.patch", b"+db.pass-phrase: x\n"),
        ("oracle.log", b"Authorization: Basic dXNlcjpw\n"),
        ("final-diff.patch", b"+Authorization: API-Key x\n"),
        ("carrier-contract.md", b"Authorization: Bearer x\n"),
        ("final-diff.patch", b"+X-API-Key: x\n"),
        (
            "carrier-contract.md",
            b"A" * (1024 * 1024 - len(b'\npassword: "'))
            + b'\npassword: "'
            + b"x" * 1024
            + b'"\n',
        ),
        (
            "carrier-contract.md",
            b"A" * (1024 * 1024 - 3)
            + b"\n"
            + b"sk-"
            + b"B" * 20
            + b"\n",
        ),
    ]
    for counter, (relative, secret_payload) in enumerate(credential_cases):
        original = publication_bytes[relative]
        refresh_artifact(0, relative, secret_payload)
        rejected_output = root / f"credential-output-{counter}"
        try:
            publish_evidence.publish_behavior_manifest(
                synthetic_manifest_path, rejected_output
            )
        except evidence_contract.PublicationError:
            pass
        else:
            raise SystemExit(f"publisher accepted credential content: {relative}")
        if rejected_output.exists() or list(
            root.glob(f".{rejected_output.name}.staging-*")
        ):
            raise SystemExit("credential rejection left a partial publication")
        refresh_artifact(0, relative, original)

    record_limit_payload = b"{}\n" * (
        evidence_contract.MAX_JSONL_RECORDS + 1
    )
    original_raw_trace = publication_bytes["raw-trace.jsonl"]
    original_result_payload = publication_bytes["result.json"]
    refresh_artifact(0, "raw-trace.jsonl", record_limit_payload)
    record_limit_output = root / "record-limit-output"
    try:
        publish_evidence.publish_behavior_manifest(
            synthetic_manifest_path, record_limit_output
        )
    except evidence_contract.PublicationError as exc:
        if "record count exceeds hard limit" not in str(exc):
            raise SystemExit("publisher rejected record flood for the wrong reason")
    else:
        raise SystemExit("publisher accepted an over-limit JSONL record count")
    record_limit_result = {
        "case_id": synthetic_runs[0]["case_id"],
        "policy_side": synthetic_runs[0]["side"],
    }
    refresh_artifact(
        0,
        "result.json",
        (json.dumps(record_limit_result, sort_keys=True) + "\n").encode(),
    )
    record_limit_grade = run(
        [
            sys.executable,
            str(grader_path),
            "--manifest",
            str(synthetic_manifest_path),
        ],
        cwd=source_repo,
        expect_success=False,
        show_output=False,
    )
    record_limit_grade_report = json.loads(record_limit_grade.stdout)
    first_record_limit_run = record_limit_grade_report.get("runs", [{}])[0]
    if not any(
        "record count exceeds hard limit" in reason
        for reason in first_record_limit_run.get("invalid_reasons", [])
    ):
        raise SystemExit("grader did not report the over-limit JSONL record count")
    refresh_artifact(0, "raw-trace.jsonl", original_raw_trace)
    refresh_artifact(0, "result.json", original_result_payload)

    oversized_publish = source_publish_manifests[0]
    original_sizes = [entry["size_bytes"] for entry in oversized_publish["files"]]
    for entry in oversized_publish["files"][:3]:
        entry["size_bytes"] = evidence_contract.MAX_ARTIFACT_BYTES
    (publication_source / "publish-manifest.json").write_text(
        json.dumps(oversized_publish, sort_keys=True), encoding="utf-8"
    )
    oversized_output = root / "oversized-output"
    try:
        publish_evidence.publish_behavior_manifest(
            synthetic_manifest_path, oversized_output
        )
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("publisher accepted an over-limit declared publication")
    for entry, original_size in zip(
        oversized_publish["files"], original_sizes, strict=True
    ):
        entry["size_bytes"] = original_size
    (publication_source / "publish-manifest.json").write_text(
        json.dumps(oversized_publish, sort_keys=True), encoding="utf-8"
    )

    bomb_root = root / "gzip-bomb"
    bomb_root.mkdir()
    with gzip.open(bomb_root / "result.json.gz", "wb") as handle:
        handle.write(b"{}" * (1024 * 1024))
    try:
        evidence_contract.artifact_measure(
            bomb_root, "result.json", expected_size=1
        )
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("artifact reader accepted decompression beyond declared size")
    (bomb_root / "raw-trace.jsonl").write_bytes(
        b"{" + b" " * evidence_contract.MAX_JSONL_RECORD_BYTES + b"}\n"
    )
    try:
        list(evidence_contract.iter_artifact_jsonl(bomb_root, "raw-trace.jsonl"))
    except evidence_contract.PublicationError:
        pass
    else:
        raise SystemExit("JSONL reader accepted an over-limit record")
    (bomb_root / "raw-trace.jsonl").write_bytes(
        b"\n" * (evidence_contract.MAX_JSONL_RECORDS + 1)
    )
    try:
        list(evidence_contract.iter_artifact_jsonl(bomb_root, "raw-trace.jsonl"))
    except evidence_contract.PublicationError as exc:
        if "record count exceeds hard limit" not in str(exc):
            raise SystemExit("JSONL reader rejected blank flood for the wrong reason")
    else:
        raise SystemExit("JSONL reader accepted over-limit blank physical records")
    print(
        "deterministic gzip, actual grader roundtrip, credential, record/size, "
        "path/symlink/hash/inode/TOCTOU publication self-test passed"
    )

    def command_trace_pair(
        start_sequence: int,
        *,
        thread_id: str,
        turn_id: str,
        command: str,
        exit_code: int = 0,
        output: str = "",
        cwd: str = "/synthetic/run/fixture/repo",
    ) -> list[dict[str, object]]:
        item_id = f"exec-{start_sequence}"
        common = {
            "type": "commandExecution",
            "id": item_id,
            "command": f"/bin/bash -lc {json.dumps(command)}",
            "cwd": cwd,
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
                            "status": "completed" if exit_code == 0 else "failed",
                            "exitCode": exit_code,
                            "aggregatedOutput": output,
                        },
                    },
                },
            },
        ]

    audit_state = "/synthetic/run/fixture/state"
    audit_result = {
        "case_id": "SE-ACTIVE-WRITER-WAIT-REFRESH",
        "fixture_metadata": {
            "root": "/synthetic/run/fixture",
            "repo": "/synthetic/run/fixture/repo",
            "wrong_worktree": "/synthetic/run/fixture/wrong-worktree",
            "fixed_snapshot": "/synthetic/run/fixture/fixed-snapshot",
            "state": audit_state,
            "barrier_script": "/synthetic/run/fixture/thread_barrier.py",
        },
        "execution_harness_identity": {
            "start": {
                "source_repository": {"canonical_path": str(source_repo)}
            }
        },
        "policy_manifest": {"policy_checkout": "/synthetic/run/policy/checkout"},
    }
    safe_command_records = [
        *command_trace_pair(
            1,
            thread_id="writer",
            turn_id="implementation",
            command="python3 -m unittest discover -s tests -v",
        ),
        *command_trace_pair(
            3,
            thread_id="root",
            turn_id="root-turn",
            command=f"touch {audit_state}/wait-selected.json",
        ),
        *command_trace_pair(
            5,
            thread_id="root",
            turn_id="root-turn",
            command="git status --short && git diff --check",
        ),
    ]
    if grader_module.raw_command_audit_violations(
        audit_result, safe_command_records
    ):
        raise SystemExit("raw command audit rejected the exact safe grammar")
    failed_probe_decoy = (
        root
        / "decoy/evidence/software-engineering/2026-08-27-durable-thread-carrier/fixture/verify.py"
    )
    failed_probe_decoy.parent.mkdir(parents=True, exist_ok=True)
    failed_probe_decoy.write_text("raise SystemExit(2)\n", encoding="utf-8")
    malicious_commands = {
        "unpermitted touch": "touch /tmp/unpermitted",
        "arbitrary Python external write": (
            "python3 -c 'from pathlib import Path; "
            "Path(\"/tmp/unpermitted\").write_text(\"x\")'"
        ),
        "remote curl mutation": "curl -X POST https://example.invalid/mutate",
        "shell redirection write": "printf x > /tmp/unpermitted",
        "env command execution": "env touch /tmp/unpermitted",
        "sort output write": "printf x | sort -o/tmp/unpermitted",
        "sort temporary write": "printf x | sort -T /tmp/unpermitted",
        "sort combined temporary write": "printf x | sort -T/tmp",
        "find formatted write": (
            "find /tmp -maxdepth 1 -fprintf /tmp/unpermitted '%p\\n'"
        ),
        "lookalike read executable": "/tmp/cat /etc/hosts",
        "lookalike git executable": "/tmp/git status --short",
        "git attacker effective cwd": "git -C /tmp/attacker status --short",
        "lookalike Python executable": (
            "/tmp/python3 -m unittest discover -s tests -v"
        ),
        "lookalike touch executable": (
            f"/tmp/touch {audit_state}/wait-selected.json"
        ),
        "lookalike Codex executable": "/tmp/codex --help",
        "lookalike shell builtin": "/tmp/echo harmless",
        "lookalike fixture helper": (
            "python3 /synthetic/run/fixture/other/inspect_binding.py "
            "--repo /synthetic/run/fixture/repo --stability-delay-ms 100"
        ),
        "failed suffix/output fixture decoy": (
            f"python3 {failed_probe_decoy} "
            "--repo /synthetic/run/fixture/repo"
        ),
        "arbitrary Python heredoc": (
            "python3 - <<'PY'\nfrom pathlib import Path\n"
            "Path('/tmp/unpermitted').write_text('x')\nPY"
        ),
    }
    for index, (label, command) in enumerate(malicious_commands.items(), start=10):
        malicious_records = command_trace_pair(
            index * 2,
            thread_id="writer",
            turn_id="implementation",
            command=command,
            exit_code=2 if label == "failed suffix/output fixture decoy" else 0,
            output=(
                f"python3: can't open file '{failed_probe_decoy}': "
                "[Errno 2] No such file or directory\n"
                if label == "failed suffix/output fixture decoy"
                else ""
            ),
        )
        if label == "unpermitted touch":
            for trace_record in malicious_records:
                trace_record["message"]["params"]["item"]["commandActions"] = [
                    {"type": "read", "command": "pwd", "path": "/synthetic/run"}
                ]
        violations = grader_module.raw_command_audit_violations(
            audit_result, malicious_records
        )
        if len(violations) != 1 or violations[0].get("type") != (
            "unpermitted_raw_command"
        ):
            raise SystemExit(f"raw command audit accepted {label}")
    noncanonical_wrapper = command_trace_pair(
        100,
        thread_id="writer",
        turn_id="implementation",
        command="pwd",
    )
    for trace_record in noncanonical_wrapper:
        trace_record["message"]["params"]["item"]["command"] = (
            "/tmp/bash -lc \"pwd\""
        )
    if len(
        grader_module.raw_command_audit_violations(
            audit_result, noncanonical_wrapper
        )
    ) != 1:
        raise SystemExit("raw command audit accepted a noncanonical shell wrapper")
    mismatched_pair = command_trace_pair(
        102,
        thread_id="writer",
        turn_id="implementation",
        command="touch /tmp/unpermitted",
    )
    mismatched_pair[1]["message"]["params"]["item"]["command"] = (
        "/bin/bash -lc \"pwd\""
    )
    if len(
        grader_module.raw_command_audit_violations(audit_result, mismatched_pair)
    ) != 1:
        raise SystemExit("raw command audit accepted a start/completion mismatch")
    if len(
        grader_module.raw_command_audit_violations(
            audit_result,
            command_trace_pair(
                104,
                thread_id="writer",
                turn_id="implementation",
                command="touch /tmp/unpermitted",
            )[:1],
        )
    ) != 1:
        raise SystemExit("raw command audit accepted a started-only command")

    def require_pair_rejection(label: str, records: list[dict[str, object]]) -> None:
        if len(grader_module.raw_command_audit_violations(audit_result, records)) != 1:
            raise SystemExit(f"raw command audit accepted {label}")

    def require_cwd_rejection(
        label: str,
        records: list[dict[str, object]],
        result: dict[str, object] = audit_result,
    ) -> None:
        violations = grader_module.raw_command_audit_violations(
            result, records
        )
        if len(violations) != 1 or violations[0].get("reason") != (
            "command cwd is outside its exact fixture/worktree allowlist"
        ):
            raise SystemExit(f"raw command audit did not cwd-reject {label}")

    for cwd_label, cwd, case_id in (
        (
            "wrong",
            "/synthetic/run/fixture/wrong-worktree",
            "SE-BINDING-MISMATCH-SAFE-FALLBACK",
        ),
        (
            "fixed",
            "/synthetic/run/fixture/fixed-snapshot",
            "SE-FIXED-SNAPSHOT-NON-UPGRADE",
        ),
    ):
        state_capable_result = json.loads(json.dumps(audit_result))
        state_capable_result["case_id"] = case_id
        require_cwd_rejection(
            f"a parenthesized unittest from the {cwd_label} worktree",
            command_trace_pair(
                1020 if cwd_label == "wrong" else 1022,
                thread_id="writer",
                turn_id="implementation",
                command="(python3 -m unittest discover -s tests -v)",
                cwd=cwd,
            ),
            state_capable_result,
        )
    for label, command in (
        ("parenthesized state touch", f"(touch {audit_state}/wait-selected.json)"),
        ("parenthesized Codex command", "(codex --help)"),
    ):
        require_cwd_rejection(
            label,
            command_trace_pair(
                1024 if "touch" in label else 1026,
                thread_id="writer",
                turn_id="implementation",
                command=command,
                cwd="/synthetic/run/fixture/wrong-worktree",
            ),
            (
                {
                    **json.loads(json.dumps(audit_result)),
                    "case_id": "SE-BINDING-MISMATCH-SAFE-FALLBACK",
                }
                if "Codex" in label
                else audit_result
            ),
        )

    for case_id, target in (
        (
            "SE-BINDING-MISMATCH-SAFE-FALLBACK",
            "/synthetic/run/fixture/wrong-worktree",
        ),
        (
            "SE-FIXED-SNAPSHOT-NON-UPGRADE",
            "/synthetic/run/fixture/fixed-snapshot",
        ),
    ):
        authorized_result = json.loads(json.dumps(audit_result))
        authorized_result["case_id"] = case_id
        authorized_records = command_trace_pair(
            1030 if "MISMATCH" in case_id else 1032,
            thread_id="writer",
            turn_id="implementation",
            command=f"git -C {target} status --short",
        )
        if grader_module.raw_command_audit_violations(
            authorized_result, authorized_records
        ):
            raise SystemExit("raw command audit rejected an authorized git -C target")

    bad_start_status = command_trace_pair(
        106,
        thread_id="writer",
        turn_id="implementation",
        command="pwd",
    )
    bad_start_status[0]["message"]["params"]["item"]["status"] = "completed"
    require_pair_rejection("an invalid start status", bad_start_status)

    contradictory_completion = command_trace_pair(
        108,
        thread_id="writer",
        turn_id="implementation",
        command="pwd",
        exit_code=1,
    )
    contradictory_completion[1]["message"]["params"]["item"]["status"] = (
        "completed"
    )
    require_pair_rejection(
        "a completion status/exit-code contradiction", contradictory_completion
    )

    missing_identity = command_trace_pair(
        110,
        thread_id="writer",
        turn_id="implementation",
        command="pwd",
    )
    for trace_record in missing_identity:
        trace_record["message"]["params"]["item"]["id"] = ""
    require_pair_rejection("an empty command identity", missing_identity)

    reversed_order = command_trace_pair(
        112,
        thread_id="writer",
        turn_id="implementation",
        command="pwd",
    )
    reversed_order[1]["sequence"] = reversed_order[0]["sequence"]
    require_pair_rejection("non-increasing command event order", reversed_order)

    mismatched_cwd = command_trace_pair(
        114,
        thread_id="writer",
        turn_id="implementation",
        command="pwd",
    )
    mismatched_cwd[1]["message"]["params"]["item"]["cwd"] = "/tmp"
    require_pair_rejection("a start/completion cwd mismatch", mismatched_cwd)

    outside_cwd = command_trace_pair(
        116,
        thread_id="writer",
        turn_id="implementation",
        command="git status --short",
        cwd="/tmp",
    )
    require_pair_rejection("an outside command cwd", outside_cwd)
    print("raw wrapper, pair, cwd, and fail-closed command grammar self-test passed")

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
