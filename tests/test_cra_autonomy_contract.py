from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "6e840c5f346ef780671825ed090d6b02b6aa73a3"
ROUTES = {"run", "skip", "approval-required", "blocked"}
ENTRY_SOURCES = {"explicit-request", "tca-required", "autonomous-risk", "none"}
CASE_EXPECTATIONS = {
    "CRA-HIGH-IMPLICIT": {
        "baseline": ("skip", "none"),
        "candidate": ("run", "autonomous-risk"),
    },
    "CRA-LOW-IMPLICIT": {
        "baseline": ("skip", "none"),
        "candidate": ("skip", "none"),
    },
    "CRA-LOW-EXPLICIT": {
        "baseline": ("run", "explicit-request"),
        "candidate": ("run", "explicit-request"),
    },
    "CRA-LOW-TCA": {
        "baseline": ("run", "tca-required"),
        "candidate": ("run", "tca-required"),
    },
    "CRA-HIGH-USER-BLOCK": {
        "baseline": ("blocked", "none"),
        "candidate": ("blocked", "none"),
    },
    "CRA-HIGH-PURCHASE": {
        "baseline": ("skip", "none"),
        "candidate": ("approval-required", "autonomous-risk"),
    },
    "CRA-HIGH-FOURTH-RUN": {
        "baseline": ("skip", "none"),
        "candidate": ("approval-required", "autonomous-risk"),
    },
}
_SHA = re.compile(r"^[0-9a-f]{40}$")
_RAW_ROUTE = re.compile(
    r"(?<![A-Za-z0-9_])route=(run|skip|approval-required|blocked)"
    r"(?![A-Za-z0-9_-])"
)
_RAW_ENTRY_SOURCE = re.compile(
    r"(?<![A-Za-z0-9_])entry_source="
    r"(explicit-request|tca-required|autonomous-risk|none)"
    r"(?![A-Za-z0-9_-])"
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _is_placeholder(value: object) -> bool:
    if not isinstance(value, str):
        return True
    normalized = value.strip().lower()
    return (
        not normalized
        or normalized
        in {"pending", "not run", "not exposed", "unknown", "n/a", "todo", "tbd"}
        or (normalized.startswith("<") and normalized.endswith(">"))
    )


def _extract_raw_decision(raw: str) -> tuple[str, str] | None:
    routes = _RAW_ROUTE.findall(raw)
    entry_sources = _RAW_ENTRY_SOURCE.findall(raw)
    if len(routes) != 1 or len(entry_sources) != 1:
        return None
    return routes[0], entry_sources[0]


def _validate_completed_record(record: str) -> list[str]:
    errors: list[str] = []
    try:
        parsed = tomllib.loads(record)
    except tomllib.TOMLDecodeError as exc:
        return [f"invalid TOML: {exc}"]

    exact_header = {
        "evaluation_id": "cra-autonomous-routing-v1",
        "status": "completed",
        "evaluator_prompt_version": "v1",
    }
    for field, expected in exact_header.items():
        if parsed.get(field) != expected:
            errors.append(f"{field} must equal {expected}")

    for field in ("model", "reasoning_effort", "tool_availability"):
        if _is_placeholder(parsed.get(field)):
            errors.append(f"{field} must be a non-placeholder string")

    baseline_commit = parsed.get("baseline_commit")
    candidate_commit = parsed.get("candidate_commit")
    if baseline_commit != BASELINE_COMMIT:
        errors.append(f"baseline_commit must equal {BASELINE_COMMIT}")
    if not isinstance(candidate_commit, str) or _SHA.fullmatch(candidate_commit) is None:
        errors.append("candidate_commit must be a 40-character lowercase SHA")
    if candidate_commit == baseline_commit:
        errors.append("candidate_commit must differ from baseline_commit")

    case_rows = parsed.get("cases")
    if not isinstance(case_rows, list):
        return errors + ["cases must be an array of tables"]

    cases: dict[str, dict[str, object]] = {}
    for index, row in enumerate(case_rows):
        if not isinstance(row, dict):
            errors.append(f"cases[{index}] must be a table")
            continue
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"cases[{index}] is missing case_id")
            continue
        if case_id in cases:
            errors.append(f"duplicate case_id: {case_id}")
            continue
        cases[case_id] = row

    expected_ids = set(CASE_EXPECTATIONS)
    actual_ids = set(cases)
    for case_id in sorted(expected_ids - actual_ids):
        errors.append(f"missing case: {case_id}")
    for case_id in sorted(actual_ids - expected_ids):
        errors.append(f"unexpected case: {case_id}")

    required = {
        "case_id",
        "baseline_raw",
        "candidate_raw",
        "normalized_baseline_route",
        "normalized_baseline_entry_source",
        "normalized_candidate_route",
        "normalized_candidate_entry_source",
        "pass",
        "hard_failure",
        "notes",
    }

    for case_id, expected in CASE_EXPECTATIONS.items():
        row = cases.get(case_id)
        if row is None:
            continue

        for field in sorted(required - set(row)):
            errors.append(f"{case_id}: missing field {field}")

        normalized = {
            "baseline": (
                row.get("normalized_baseline_route"),
                row.get("normalized_baseline_entry_source"),
            ),
            "candidate": (
                row.get("normalized_candidate_route"),
                row.get("normalized_candidate_entry_source"),
            ),
        }
        for version, (route, entry_source) in normalized.items():
            if route not in ROUTES:
                errors.append(f"{case_id}: normalized_{version}_route is invalid")
            if entry_source not in ENTRY_SOURCES:
                errors.append(
                    f"{case_id}: normalized_{version}_entry_source is invalid"
                )

        for version in ("baseline", "candidate"):
            raw = row.get(f"{version}_raw")
            if _is_placeholder(raw):
                errors.append(
                    f"{case_id}: {version}_raw must contain non-placeholder output"
                )
                continue
            assert isinstance(raw, str)
            raw_decision = _extract_raw_decision(raw)
            if raw_decision is None:
                errors.append(
                    f"{case_id}: {version}_raw must contain exactly one route "
                    "and one entry_source"
                )
            elif raw_decision != normalized[version]:
                errors.append(
                    f"{case_id}: {version}_raw does not match normalized fields"
                )

            if normalized[version] != expected[version]:
                errors.append(
                    f"{case_id}: normalized {version} decision does not match "
                    "the accepted route"
                )

        if row.get("pass") is not True:
            errors.append(f"{case_id}: pass must be true")
        if row.get("hard_failure") is not False:
            errors.append(f"{case_id}: hard_failure must be false")
        if _is_placeholder(row.get("notes")):
            errors.append(f"{case_id}: notes must be non-placeholder")

    return errors


def _build_synthetic_completed_record(
    overrides: dict[tuple[str, str], object] | None = None,
) -> str:
    overrides = overrides or {}
    lines = [
        'evaluation_id = "cra-autonomous-routing-v1"',
        'status = "completed"',
        'model = "test-model"',
        'reasoning_effort = "high"',
        'tool_availability = "isolated-read-only"',
        f'baseline_commit = "{BASELINE_COMMIT}"',
        f'candidate_commit = "{"1" * 40}"',
        'evaluator_prompt_version = "v1"',
    ]

    for case_id, expected in CASE_EXPECTATIONS.items():
        row: dict[str, object] = {
            "case_id": case_id,
            "baseline_raw": (
                f"route={expected['baseline'][0]}\n"
                f"entry_source={expected['baseline'][1]}\n"
                "reason=synthetic baseline"
            ),
            "candidate_raw": (
                f"route={expected['candidate'][0]}\n"
                f"entry_source={expected['candidate'][1]}\n"
                "reason=synthetic candidate"
            ),
            "normalized_baseline_route": expected["baseline"][0],
            "normalized_baseline_entry_source": expected["baseline"][1],
            "normalized_candidate_route": expected["candidate"][0],
            "normalized_candidate_entry_source": expected["candidate"][1],
            "pass": True,
            "hard_failure": False,
            "notes": "synthetic validator fixture",
        }
        for (override_case, field), value in overrides.items():
            if override_case == case_id:
                if value is None:
                    row.pop(field, None)
                else:
                    row[field] = value

        lines.append("")
        lines.append("[[cases]]")
        for field, value in row.items():
            if isinstance(value, bool):
                encoded = "true" if value else "false"
            else:
                encoded = json.dumps(value, ensure_ascii=False)
            lines.append(f"{field} = {encoded}")

    return "\n".join(lines) + "\n"


class CraAutonomyContractTests(unittest.TestCase):
    def test_cra_can_be_selected_without_an_explicit_user_request(self) -> None:
        skill = read("skills/software-engineering/SKILL.md")
        cra_reference = read("skills/software-engineering/references/cra-loop.md")
        contract = "\n".join((skill, cra_reference))

        for statement in (
            "autonomous CRA selection and CRA/TCA loops",
            "choose and record exactly one route",
            "for every completed task unit, regardless of complexity",
            "`run`: enter CRA now.",
            "`skip`: independent commit-level review has low expected value",
            "`approval-required`: CRA is warranted",
            "`blocked`: CRA cannot start safely",
            "Presume `autonomous-risk` is warranted",
            "Do not ask again solely because the user did not name CRA",
            "autonomous-risk",
        ):
            self.assertIn(statement, contract)

        self.assertNotIn(
            "Use only when the user explicitly requests `CRA 루프`.",
            skill,
        )
        self.assertNotIn(
            "Use this reference only when the user explicitly requests `CRA 루프`.",
            cra_reference,
        )

    def test_explicit_and_tca_entries_override_low_value_skip(self) -> None:
        skill = read("skills/software-engineering/SKILL.md")
        cra_reference = read("skills/software-engineering/references/cra-loop.md")
        contract = "\n".join((skill, cra_reference))

        for statement in (
            "A trivial task with no explicit or TCA requirement will normally be `skip`",
            "An `explicit-request` or `tca-required` entry produces `run` even for a typo",
            "The low-value skip rule applies only to `autonomous-risk`.",
            "The low-value autonomous skip rule never cancels `explicit-request` or `tca-required`.",
        ):
            self.assertIn(statement, contract)

    def test_autonomous_usage_has_a_bounded_standing_approval(self) -> None:
        agents = read("AGENTS.md")
        skill = read("skills/software-engineering/SKILL.md")
        cra_reference = read("skills/software-engineering/references/cra-loop.md")
        contract = "\n".join((agents, skill, cra_reference))

        for statement in (
            "상시 승인은 그 범위 안에서 명시적 승인으로 본다.",
            "The user's decision to enable autonomous CRA is a bounded standing approval",
            "at most three reviewer command invocations per task unit",
            "purchasing credits",
            "starting a fourth reviewer invocation",
            "Count an invocation when the reviewer command is launched",
            "Local mutation authority and inference-usage authority are separate.",
            "do not launch a substitute merely because it is the closest available flow",
            "If any item is different or unknown, do not launch it; return route `approval-required`",
        ):
            self.assertIn(statement, contract)

    def test_autonomous_cra_does_not_expand_tca_or_remote_authority(self) -> None:
        skill = read("skills/software-engineering/SKILL.md")
        cra_reference = read("skills/software-engineering/references/cra-loop.md")
        tca_reference = read("skills/software-engineering/references/tca-loop.md")

        self.assertIn(
            "Autonomous CRA selection does not authorize starting TCA.",
            skill,
        )
        self.assertIn(
            "Use only when the user explicitly requests `TCA 루프`.",
            skill,
        )
        self.assertIn(
            "Use this reference only when the user explicitly requests `TCA 루프`.",
            tca_reference,
        )
        self.assertIn(
            "A local commit is not approval to push, deploy, migrate",
            cra_reference,
        )

    def test_tca_records_and_resumes_approval_required(self) -> None:
        tca_reference = read("skills/software-engineering/references/tca-loop.md")
        cra_reference = read("skills/software-engineering/references/cra-loop.md")
        contract = "\n".join((tca_reference, cra_reference))

        for statement in (
            "`approval-pending`",
            "does not satisfy the CRA terminal-state gate",
            "record the current task ID, commit SHA, CRA entry source",
            "resume the same task at the CRA usage-authorization check",
            "Do not select or implement the next task while approval is pending.",
            "This is a pause route, not a terminal review state.",
        ):
            self.assertIn(statement, contract)

    def test_skip_and_pre_invocation_routes_are_user_visible(self) -> None:
        skill = read("skills/software-engineering/SKILL.md")
        for statement in (
            "Keep the route decision user-visible",
            "including an explicit `skip` decision",
            "report the CRA route, entry source, and concise rationale",
        ):
            self.assertIn(statement, skill)

    def test_routing_evaluation_covers_representative_behavior(self) -> None:
        evaluation = read(
            "skills/software-engineering/references/cra-routing-evaluation.md"
        )
        references_index = read("skills/software-engineering/references/README.md")

        self.assertIn("cra-routing-evaluation.md", references_index)
        for case_id in CASE_EXPECTATIONS:
            self.assertIn(case_id, evaluation)

        for statement in (
            "Start a fresh agent context",
            "Use the same model, reasoning effort, tool availability, and evaluator prompt",
            "Candidate prompt: `route=run`, `entry_source=autonomous-risk`.",
            "Candidate prompt: `route=skip`, `entry_source=none`.",
            "Candidate prompt: `route=run`, `entry_source=explicit-request`.",
            "Candidate prompt: `route=run`, `entry_source=tca-required`.",
            "Candidate prompt: `route=blocked`, `entry_source=none`.",
            "Candidate prompt: `route=approval-required`, `entry_source=autonomous-risk`.",
            "This autonomous CRA routing change is not ready to merge until a completed behavior record exists",
            "A failing gate is the correct repository state when no authorized isolated model execution environment is available.",
            "Each `[[cases]]` table is validated independently.",
            "They do not replace the isolated behavior run.",
        ):
            self.assertIn(statement, evaluation)

    def test_record_validator_binds_results_to_each_case(self) -> None:
        self.assertEqual(
            _validate_completed_record(_build_synthetic_completed_record()),
            [],
        )

        invalid_records = (
            (
                {("CRA-HIGH-IMPLICIT", "baseline_raw"): ""},
                "baseline_raw must contain non-placeholder output",
            ),
            (
                {("CRA-HIGH-IMPLICIT", "normalized_candidate_route"): None},
                "missing field normalized_candidate_route",
            ),
            (
                {("CRA-LOW-IMPLICIT", "pass"): False},
                "pass must be true",
            ),
            (
                {("CRA-LOW-TCA", "hard_failure"): True},
                "hard_failure must be false",
            ),
            (
                {
                    ("CRA-HIGH-PURCHASE", "candidate_raw"): (
                        "route=skip\n"
                        "entry_source=none\n"
                        "reason=does not match normalized fields"
                    )
                },
                "candidate_raw does not match normalized fields",
            ),
        )
        for overrides, expected_error in invalid_records:
            with self.subTest(expected_error=expected_error):
                errors = _validate_completed_record(
                    _build_synthetic_completed_record(overrides)
                )
                self.assertTrue(
                    any(expected_error in error for error in errors),
                    errors,
                )

    def test_completed_routing_evaluation_record_exists_before_merge(self) -> None:
        record_path = (
            ROOT
            / "skills"
            / "software-engineering"
            / "evals"
            / "cra-autonomous-routing-v1.toml"
        )
        self.assertTrue(
            record_path.is_file(),
            "CRA routing behavior evaluation is required before merge: "
            "run the isolated baseline/candidate matrix and write "
            "skills/software-engineering/evals/cra-autonomous-routing-v1.toml",
        )

        errors = _validate_completed_record(
            record_path.read_text(encoding="utf-8")
        )
        self.assertEqual(
            errors,
            [],
            "CRA routing evaluation record is incomplete or inconsistent:\n"
            + "\n".join(f"- {error}" for error in errors),
        )


if __name__ == "__main__":
    unittest.main()
