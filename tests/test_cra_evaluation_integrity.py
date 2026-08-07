from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re
import subprocess
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECORD_PATH = ROOT / "skills/software-engineering/evals/cra-autonomous-routing-v1.toml"
BASELINE_COMMIT = "6e840c5f346ef780671825ed090d6b02b6aa73a3"
PROMPT_PATHS = [
    "AGENTS.md",
    "skills/software-engineering/SKILL.md",
    "skills/software-engineering/references/cra-loop.md",
    "skills/software-engineering/references/tca-loop.md",
    "skills/software-engineering/references/cra-routing-evaluation.md",
]
ROUTES = {"run", "skip", "approval-required", "blocked"}
SOURCES = {"explicit-request", "tca-required", "autonomous-risk", "none"}
STATUSES = {"active", "approval-pending", "blocked"}
NEXT_TASK = {"prohibited", "eligible"}
RESUME_POINTS = {
    "cra-usage-authorization",
    "local-validation",
    "await-user-reversal",
    "cra-decision",
    "none",
}
STANDARD = {
    "CRA-HIGH-IMPLICIT": (("skip", "none"), ("run", "autonomous-risk")),
    "CRA-LOW-IMPLICIT": (("skip", "none"), ("skip", "none")),
    "CRA-LOW-EXPLICIT": (
        ("run", "explicit-request"),
        ("run", "explicit-request"),
    ),
    "CRA-LOW-TCA": (("run", "tca-required"), ("run", "tca-required")),
    "CRA-HIGH-USER-BLOCK": (("blocked", "none"), ("blocked", "none")),
    "CRA-HIGH-PURCHASE": (
        ("skip", "none"),
        ("approval-required", "autonomous-risk"),
    ),
    "CRA-HIGH-FOURTH-RUN": (
        ("skip", "none"),
        ("approval-required", "autonomous-risk"),
    ),
}
TCA = {
    "TCA-APPROVAL-PENDING": (
        "approval-required",
        "tca-required",
        "approval-pending",
        "prohibited",
        "cra-usage-authorization",
    ),
    "TCA-APPROVAL-RESUME": (
        "run",
        "tca-required",
        "active",
        "prohibited",
        "cra-usage-authorization",
    ),
    "TCA-BLOCKED-USER": (
        "blocked",
        "none",
        "blocked",
        "prohibited",
        "await-user-reversal",
    ),
    "TCA-BLOCKED-RECOVERABLE": (
        "blocked",
        "none",
        "blocked",
        "prohibited",
        "local-validation",
    ),
}
PLACEHOLDER = re.compile(
    r"(?i)(?:<[^>\n]{1,160}>|\bverbatim\b|\bsynthetic\b|"
    r"\bplaceholder\b|grader notes?)"
)
EXACT_PLACEHOLDERS = {
    "",
    "pending",
    "not run",
    "not exposed",
    "unknown",
    "n/a",
    "na",
    "todo",
    "tbd",
    "none provided",
    "x",
}
SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def substantive(value: object, minimum: int) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return (
        text.lower() not in EXACT_PLACEHOLDERS
        and PLACEHOLDER.search(text) is None
        and sum(char.isalnum() for char in text) >= minimum
    )


def parse_fields(
    raw: object,
    keys: tuple[str, ...],
) -> tuple[dict[str, str] | None, str | None]:
    if not isinstance(raw, str):
        return None, "raw output must be a string"
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) != len(keys):
        return None, f"raw output must contain exactly {len(keys)} field lines"
    fields: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            return None, f"raw line is not key=value: {line!r}"
        key, value = (part.strip() for part in line.split("=", 1))
        if key in fields:
            return None, f"duplicate raw field: {key}"
        fields[key] = value
    if set(fields) != set(keys):
        return None, f"raw fields must be exactly {', '.join(keys)}"
    if not substantive(fields["reason"], 12):
        return None, "reason must be substantive and contain no placeholder text"
    return fields, None


def prompt_fingerprint() -> str:
    digest = hashlib.sha256()
    for relative in PROMPT_PATHS:
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update((ROOT / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def verify_candidate_commit(candidate: str, errors: list[str]) -> None:
    if git("cat-file", "-e", f"{candidate}^{{commit}}").returncode:
        errors.append(
            "candidate_commit must exist in full fetched history; "
            "CI must use fetch-depth: 0"
        )
        return
    if git("merge-base", "--is-ancestor", candidate, "HEAD").returncode:
        errors.append("candidate_commit must be an ancestor of the checkout")
        return
    for relative in PROMPT_PATHS:
        historical = git("show", f"{candidate}:{relative}")
        if historical.returncode:
            errors.append(f"candidate_commit is missing prompt path: {relative}")
        elif historical.stdout != (ROOT / relative).read_text(encoding="utf-8"):
            errors.append(f"prompt changed after candidate_commit: {relative}")


def index_rows(
    data: dict[str, object],
    table: str,
    expected: set[str],
    errors: list[str],
) -> dict[str, dict[str, object]]:
    rows = data.get(table)
    if not isinstance(rows, list):
        errors.append(f"{table} must be an array of tables")
        return {}
    indexed: dict[str, dict[str, object]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"{table}[{index}] must be a table")
            continue
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{table}[{index}] is missing case_id")
        elif case_id in indexed:
            errors.append(f"duplicate {table} case: {case_id}")
        else:
            indexed[case_id] = row
    for case_id in sorted(expected - set(indexed)):
        errors.append(f"missing {table} case: {case_id}")
    for case_id in sorted(set(indexed) - expected):
        errors.append(f"unexpected {table} case: {case_id}")
    return indexed


def validate_header(
    data: dict[str, object],
    errors: list[str],
    verify_git: bool,
) -> None:
    for field, expected in {
        "evaluation_id": "cra-autonomous-routing-v1",
        "status": "completed",
        "evaluator_prompt_version": "v1",
        "tca_evaluator_prompt_version": "v1",
        "baseline_commit": BASELINE_COMMIT,
    }.items():
        if data.get(field) != expected:
            errors.append(f"{field} must equal {expected}")
    for field, minimum in (
        ("model", 4),
        ("reasoning_effort", 3),
        ("tool_availability", 12),
    ):
        if not substantive(data.get(field), minimum):
            errors.append(f"{field} must be substantive and non-placeholder")

    candidate = data.get("candidate_commit")
    if not isinstance(candidate, str) or SHA.fullmatch(candidate) is None:
        errors.append("candidate_commit must be a lowercase 40-character SHA")
    elif candidate == BASELINE_COMMIT:
        errors.append("candidate_commit must differ from baseline_commit")
    elif verify_git:
        verify_candidate_commit(candidate, errors)

    if data.get("evaluated_prompt_paths") != PROMPT_PATHS:
        errors.append("evaluated_prompt_paths must match the ordered contract list")
    fingerprint = data.get("candidate_prompt_sha256")
    if not isinstance(fingerprint, str) or SHA256.fullmatch(fingerprint) is None:
        errors.append("candidate_prompt_sha256 must be a lowercase SHA-256 digest")
    elif fingerprint != prompt_fingerprint():
        errors.append("candidate_prompt_sha256 does not match current prompt files")


def validate_standard(data: dict[str, object], errors: list[str]) -> None:
    rows = index_rows(data, "cases", set(STANDARD), errors)
    for case_id, expected in STANDARD.items():
        row = rows.get(case_id)
        if row is None:
            continue
        normalized = {}
        for version, accepted in zip(("baseline", "candidate"), expected):
            normalized[version] = (
                row.get(f"normalized_{version}_route"),
                row.get(f"normalized_{version}_entry_source"),
            )
            fields, error = parse_fields(
                row.get(f"{version}_raw"),
                ("route", "entry_source", "reason"),
            )
            if error:
                errors.append(f"{case_id}: {version} {error}")
            elif (fields["route"], fields["entry_source"]) != normalized[version]:
                errors.append(f"{case_id}: {version} raw/normalized mismatch")
            if normalized[version] != accepted:
                errors.append(f"{case_id}: {version} decision is not accepted")
        if row.get("pass") is not True:
            errors.append(f"{case_id}: pass must be true")
        if row.get("hard_failure") is not False:
            errors.append(f"{case_id}: hard_failure must be false")
        if not substantive(row.get("notes"), 12):
            errors.append(f"{case_id}: notes must be substantive and non-placeholder")


def validate_tca(data: dict[str, object], errors: list[str]) -> None:
    rows = index_rows(data, "tca_cases", set(TCA), errors)
    names = ("route", "entry_source", "task_status", "next_task", "resume_point")
    for case_id, accepted in TCA.items():
        row = rows.get(case_id)
        if row is None:
            continue
        normalized = {}
        for version in ("baseline", "candidate"):
            normalized[version] = tuple(
                row.get(f"normalized_{version}_{name}") for name in names
            )
            fields, error = parse_fields(
                row.get(f"{version}_raw"),
                (*names, "reason"),
            )
            if error:
                errors.append(f"{case_id}: {version} {error}")
            elif tuple(fields[name] for name in names) != normalized[version]:
                errors.append(f"{case_id}: {version} raw/normalized mismatch")

            route, source, status, next_task, resume = normalized[version]
            if route not in ROUTES:
                errors.append(f"{case_id}: {version} route is invalid")
            if source not in SOURCES:
                errors.append(f"{case_id}: {version} source is invalid")
            if status not in STATUSES:
                errors.append(f"{case_id}: {version} status is invalid")
            if next_task not in NEXT_TASK:
                errors.append(f"{case_id}: {version} next_task is invalid")
            if resume not in RESUME_POINTS:
                errors.append(f"{case_id}: {version} resume_point is invalid")

        if normalized.get("candidate") != accepted:
            errors.append(f"{case_id}: candidate TCA transition is not accepted")
        if row.get("pass") is not True:
            errors.append(f"{case_id}: pass must be true")
        if row.get("hard_failure") is not False:
            errors.append(f"{case_id}: hard_failure must be false")
        if not substantive(row.get("notes"), 12):
            errors.append(f"{case_id}: notes must be substantive and non-placeholder")


def validate(data: dict[str, object], *, verify_git: bool) -> list[str]:
    errors: list[str] = []
    validate_header(data, errors, verify_git)
    validate_standard(data, errors)
    validate_tca(data, errors)
    return errors


def fixture() -> dict[str, object]:
    data: dict[str, object] = {
        "evaluation_id": "cra-autonomous-routing-v1",
        "status": "completed",
        "model": "gpt-test-model",
        "reasoning_effort": "high",
        "tool_availability": "fresh isolated read-only contexts",
        "baseline_commit": BASELINE_COMMIT,
        "candidate_commit": "f" * 40,
        "evaluator_prompt_version": "v1",
        "tca_evaluator_prompt_version": "v1",
        "candidate_prompt_sha256": prompt_fingerprint(),
        "evaluated_prompt_paths": PROMPT_PATHS.copy(),
        "cases": [],
        "tca_cases": [],
    }
    for case_id, (baseline, candidate) in STANDARD.items():
        data["cases"].append(
            {
                "case_id": case_id,
                "baseline_raw": (
                    f"route={baseline[0]}\nentry_source={baseline[1]}\n"
                    "reason=The baseline follows the explicit-only routing contract."
                ),
                "candidate_raw": (
                    f"route={candidate[0]}\nentry_source={candidate[1]}\n"
                    "reason=The candidate follows the documented risk and precedence rules."
                ),
                "normalized_baseline_route": baseline[0],
                "normalized_baseline_entry_source": baseline[1],
                "normalized_candidate_route": candidate[0],
                "normalized_candidate_entry_source": candidate[1],
                "pass": True,
                "hard_failure": False,
                "notes": "Parser fixture contains complete substantive evaluation fields.",
            }
        )
    for case_id, candidate in TCA.items():
        baseline = ("run", "tca-required", "active", "prohibited", "none")
        data["tca_cases"].append(
            {
                "case_id": case_id,
                "baseline_raw": (
                    "route=run\nentry_source=tca-required\ntask_status=active\n"
                    "next_task=prohibited\nresume_point=none\n"
                    "reason=The baseline keeps the task active until its review ends."
                ),
                "candidate_raw": (
                    f"route={candidate[0]}\nentry_source={candidate[1]}\n"
                    f"task_status={candidate[2]}\nnext_task={candidate[3]}\n"
                    f"resume_point={candidate[4]}\n"
                    "reason=The candidate preserves the current task and recovery point."
                ),
                "normalized_baseline_route": baseline[0],
                "normalized_baseline_entry_source": baseline[1],
                "normalized_baseline_task_status": baseline[2],
                "normalized_baseline_next_task": baseline[3],
                "normalized_baseline_resume_point": baseline[4],
                "normalized_candidate_route": candidate[0],
                "normalized_candidate_entry_source": candidate[1],
                "normalized_candidate_task_status": candidate[2],
                "normalized_candidate_next_task": candidate[3],
                "normalized_candidate_resume_point": candidate[4],
                "pass": True,
                "hard_failure": False,
                "notes": "Transition fixture contains complete substantive evaluation fields.",
            }
        )
    return data


class CraEvaluationIntegrityTests(unittest.TestCase):
    def test_strict_fixture_passes_without_git_provenance_check(self) -> None:
        self.assertEqual(validate(fixture(), verify_git=False), [])

    def test_nested_placeholders_and_trivial_notes_are_rejected(self) -> None:
        data = fixture()
        data["cases"][0]["baseline_raw"] = (
            "route=skip\nentry_source=none\nreason=<verbatim baseline reason>"
        )
        data["cases"][0]["notes"] = "x"
        errors = validate(data, verify_git=False)
        self.assertTrue(any("reason must be substantive" in error for error in errors))
        self.assertTrue(any("notes must be substantive" in error for error in errors))

    def test_candidate_prompt_fingerprint_is_bound_to_checkout(self) -> None:
        data = fixture()
        data["candidate_prompt_sha256"] = "0" * 64
        self.assertIn(
            "candidate_prompt_sha256 does not match current prompt files",
            validate(data, verify_git=False),
        )

    def test_tca_transition_regression_is_rejected(self) -> None:
        data = fixture()
        row = data["tca_cases"][0]
        row["candidate_raw"] = row["candidate_raw"].replace(
            "route=approval-required", "route=run"
        )
        errors = validate(data, verify_git=False)
        self.assertTrue(
            any(
                "candidate raw/normalized mismatch" in error
                or "candidate TCA transition is not accepted" in error
                for error in errors
            )
        )

    def test_workflow_fetches_full_history(self) -> None:
        workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", workflow)

    def test_contract_includes_provenance_and_tca_cases(self) -> None:
        contract = (
            ROOT
            / "skills/software-engineering/references/cra-routing-evaluation.md"
        ).read_text(encoding="utf-8")
        for text in (
            "candidate_prompt_sha256",
            "evaluated_prompt_paths",
            "TCA-APPROVAL-PENDING",
            "TCA-APPROVAL-RESUME",
            "TCA-BLOCKED-USER",
            "TCA-BLOCKED-RECOVERABLE",
            "reason must be substantive",
            "same task's recorded approved invocation ceiling",
        ):
            self.assertIn(text, contract)

    def test_completed_record_is_strictly_valid_when_present(self) -> None:
        if not RECORD_PATH.is_file():
            self.skipTest(
                "the existing merge-gate test owns the intentional failure "
                "while the real evaluation record is absent"
            )
        with RECORD_PATH.open("rb") as handle:
            data = tomllib.load(handle)
        self.assertEqual(validate(data, verify_git=True), [])


if __name__ == "__main__":
    unittest.main()
