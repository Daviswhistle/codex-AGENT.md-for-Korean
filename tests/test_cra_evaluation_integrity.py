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
CASE_GROUNDING_TERMS = {
    "CRA-HIGH-IMPLICIT": (
        "authentication",
        "auth token",
        "token refresh",
        "concurr",
        "caller",
        "failure path",
        "인증",
        "토큰",
        "동시",
        "호출자",
        "실패 경로",
    ),
    "CRA-LOW-IMPLICIT": (
        "readme",
        "typo",
        "format",
        "link",
        "mechanical",
        "focused validation",
        "오탈자",
        "포맷",
        "링크",
        "기계적",
        "집중 검증",
    ),
    "CRA-LOW-EXPLICIT": (
        "readme",
        "typo",
        "explicit request",
        "user request",
        "오탈자",
        "명시 요청",
        "사용자 요청",
    ),
    "CRA-LOW-TCA": (
        "tca",
        "task gate",
        "review gate",
        "required review",
        "게이트",
        "필수 리뷰",
        "종결 상태",
    ),
    "CRA-HIGH-USER-BLOCK": (
        "user prohibition",
        "user forbids",
        "forbids review",
        "user instruction",
        "no commit",
        "no review",
        "사용자 금지",
        "커밋 금지",
        "리뷰 금지",
        "하지 말",
    ),
    "CRA-HIGH-PURCHASE": (
        "migration",
        "persisted data",
        "credit purchase",
        "billing",
        "purchase",
        "마이그레이션",
        "영속 데이터",
        "크레딧",
        "과금",
        "구매",
    ),
    "CRA-HIGH-FOURTH-RUN": (
        "fourth invocation",
        "fourth reviewer",
        "three invocation",
        "invocation ceiling",
        "usage ceiling",
        "네 번째",
        "세 번",
        "호출 상한",
        "사용량 상한",
    ),
    "TCA-APPROVAL-PENDING": (
        "fourth invocation",
        "fourth-invocation",
        "approval-pending",
        "usage ceiling",
        "next task",
        "네 번째",
        "승인 대기",
        "사용량 상한",
        "다음 task",
    ),
    "TCA-APPROVAL-RESUME": (
        "approved ceiling",
        "approved-ceiling",
        "fourth invocation",
        "same task",
        "usage-authorization",
        "승인 상한",
        "네 번째",
        "같은 task",
        "사용 승인",
    ),
    "TCA-BLOCKED-USER": (
        "user prohibition",
        "user forbids",
        "user reversal",
        "await-user-reversal",
        "사용자 금지",
        "명시적 철회",
        "사용자 철회",
    ),
    "TCA-BLOCKED-RECOVERABLE": (
        "missing validation",
        "local validation",
        "recoverable blocker",
        "local-validation",
        "검증 누락",
        "로컬 검증",
        "회복 가능한",
    ),
}
GRADER_NOTE_TERMS = (
    "raw",
    "normalized",
    "accepted",
    "expected",
    "route",
    "entry source",
    "transition",
    "원문",
    "정규화",
    "기대값",
    "경로",
    "진입 원인",
    "전이",
)
PLACEHOLDER = re.compile(
    r"(?is)(?:"
    r"<[^>\n]{1,240}>"
    r"|\{\{[^}\n]{1,240}\}\}"
    r"|\$\{[^}\n]{1,240}\}"
    r"|\[\[[^\]\n]{1,240}\]\]"
    r"|^\s*\[[^\]\n]{1,240}\]\s*$"
    r"|^\s*\{[^{}\n]{1,240}\}\s*$"
    r"|\bverbatim\b|\bsynthetic\b|\bplaceholder\b|grader notes?"
    r"|\bone substantive sentence\b"
    r"|\bexplain(?: the)?(?: grader)? disposition(?: here)?\b"
    r")"
)
LETTER_WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
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
TERMINAL_PUNCTUATION = (".", "!", "?", "。", "！", "？")
SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def substantive(
    value: object,
    minimum: int,
    *,
    natural_language: bool = False,
) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if (
        text.lower() in EXACT_PLACEHOLDERS
        or PLACEHOLDER.search(text) is not None
        or sum(char.isalnum() for char in text) < minimum
    ):
        return False
    if not natural_language:
        return True

    words = LETTER_WORD.findall(text)
    letter_count = sum(char.isalpha() for char in text)
    distinct_words = {word.casefold() for word in words}
    return (
        text.endswith(TERMINAL_PUNCTUATION)
        and letter_count >= max(16, minimum)
        and len(words) >= 4
        and len(distinct_words) >= 4
    )


def explanation_key(value: str) -> str:
    words = LETTER_WORD.findall(value.casefold())
    return " ".join(words)


def reason_is_grounded(case_id: str, reason: str) -> bool:
    if not substantive(reason, 16, natural_language=True):
        return False
    lowered = reason.casefold()
    return any(term.casefold() in lowered for term in CASE_GROUNDING_TERMS[case_id])


def notes_are_case_specific(case_id: str, notes: object) -> bool:
    if not substantive(notes, 20, natural_language=True):
        return False
    assert isinstance(notes, str)
    lowered = notes.casefold()
    return case_id.casefold() in lowered and any(
        term.casefold() in lowered for term in GRADER_NOTE_TERMS
    )


def parse_fields(
    raw: object,
    keys: tuple[str, ...],
    *,
    case_id: str,
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
    if not reason_is_grounded(case_id, fields["reason"]):
        return None, "reason must be a complete case-grounded sentence"
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


def git_bytes(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )


def prompt_bytes_equal(historical: bytes, current: bytes) -> bool:
    return historical == current


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
        historical = git_bytes("show", f"{candidate}:{relative}")
        if historical.returncode:
            errors.append(f"candidate_commit is missing prompt path: {relative}")
        elif not prompt_bytes_equal(
            historical.stdout,
            (ROOT / relative).read_bytes(),
        ):
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


def register_unique_reason(
    reasons: dict[str, tuple[str, str]],
    case_id: str,
    version: str,
    reason: str,
    errors: list[str],
) -> None:
    key = explanation_key(reason)
    previous = reasons.get(key)
    if previous is not None and previous[0] != case_id:
        errors.append(
            f"{case_id}: {version} reason is reused from "
            f"{previous[0]} {previous[1]}"
        )
    else:
        reasons[key] = (case_id, version)


def register_unique_notes(
    notes_seen: dict[str, str],
    case_id: str,
    notes: str,
    errors: list[str],
) -> None:
    key = explanation_key(notes)
    previous = notes_seen.get(key)
    if previous is not None and previous != case_id:
        errors.append(f"{case_id}: notes are reused from {previous}")
    else:
        notes_seen[key] = case_id


def validate_standard(
    data: dict[str, object],
    errors: list[str],
    reasons: dict[str, tuple[str, str]],
    notes_seen: dict[str, str],
) -> None:
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
                case_id=case_id,
            )
            if error:
                errors.append(f"{case_id}: {version} {error}")
            else:
                assert fields is not None
                register_unique_reason(
                    reasons,
                    case_id,
                    version,
                    fields["reason"],
                    errors,
                )
                if (fields["route"], fields["entry_source"]) != normalized[version]:
                    errors.append(f"{case_id}: {version} raw/normalized mismatch")
            if normalized[version] != accepted:
                errors.append(f"{case_id}: {version} decision is not accepted")
        if row.get("pass") is not True:
            errors.append(f"{case_id}: pass must be true")
        if row.get("hard_failure") is not False:
            errors.append(f"{case_id}: hard_failure must be false")
        notes = row.get("notes")
        if not notes_are_case_specific(case_id, notes):
            errors.append(
                f"{case_id}: notes must be a complete case-specific grader sentence"
            )
        else:
            assert isinstance(notes, str)
            register_unique_notes(notes_seen, case_id, notes, errors)


def validate_tca(
    data: dict[str, object],
    errors: list[str],
    reasons: dict[str, tuple[str, str]],
    notes_seen: dict[str, str],
) -> None:
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
                case_id=case_id,
            )
            if error:
                errors.append(f"{case_id}: {version} {error}")
            else:
                assert fields is not None
                register_unique_reason(
                    reasons,
                    case_id,
                    version,
                    fields["reason"],
                    errors,
                )
                if tuple(fields[name] for name in names) != normalized[version]:
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
        notes = row.get("notes")
        if not notes_are_case_specific(case_id, notes):
            errors.append(
                f"{case_id}: notes must be a complete case-specific grader sentence"
            )
        else:
            assert isinstance(notes, str)
            register_unique_notes(notes_seen, case_id, notes, errors)


def validate(data: dict[str, object], *, verify_git: bool) -> list[str]:
    errors: list[str] = []
    reasons: dict[str, tuple[str, str]] = {}
    notes_seen: dict[str, str] = {}
    validate_header(data, errors, verify_git)
    validate_standard(data, errors, reasons, notes_seen)
    validate_tca(data, errors, reasons, notes_seen)
    return errors


STANDARD_REASONS = {
    "CRA-HIGH-IMPLICIT": (
        "The baseline skips because no explicit request covers the authentication and concurrency change.",
        "Authentication and concurrent failure paths make independent commit review materially valuable.",
    ),
    "CRA-LOW-IMPLICIT": (
        "The baseline skips because the README typo has no explicit review request.",
        "The README typo is mechanical and focused validation fully establishes the changed contract.",
    ),
    "CRA-LOW-EXPLICIT": (
        "The explicit user request requires review even though the README typo is mechanically small.",
        "The candidate honors the explicit request and runs review for the README typo.",
    ),
    "CRA-LOW-TCA": (
        "The TCA task gate requires a completed review before queue progression can continue.",
        "The candidate runs review because the TCA review gate is mandatory for this task.",
    ),
    "CRA-HIGH-USER-BLOCK": (
        "The user prohibition on commits and review blocks the baseline from entering CRA.",
        "The latest user instruction forbids review, so the candidate must return a blocked route.",
    ),
    "CRA-HIGH-PURCHASE": (
        "The baseline skips because no explicit request authorizes review of the data migration.",
        "The migration review requires a credit purchase or billing change, so approval is required.",
    ),
    "CRA-HIGH-FOURTH-RUN": (
        "The baseline skips because no explicit request covers the fourth reviewer invocation.",
        "The fourth invocation exceeds the standing usage ceiling and therefore needs additional approval.",
    ),
}
TCA_BASELINE_REASONS = {
    "TCA-APPROVAL-PENDING": (
        "The baseline keeps the TCA task active because it lacks a fourth-invocation ceiling transition.",
    ),
    "TCA-APPROVAL-RESUME": (
        "The baseline keeps the TCA task active because it has no approved-ceiling resume contract.",
    ),
    "TCA-BLOCKED-USER": (
        "The baseline keeps the TCA task active despite the user prohibition because no blocker state exists.",
    ),
    "TCA-BLOCKED-RECOVERABLE": (
        "The baseline keeps the TCA task active despite missing local validation and no recovery state.",
    ),
}
TCA_CANDIDATE_REASONS = {
    "TCA-APPROVAL-PENDING": (
        "The fourth invocation exceeds the TCA usage ceiling, so the task enters approval-pending.",
    ),
    "TCA-APPROVAL-RESUME": (
        "The approved ceiling covers the fourth invocation and resumes the same task at usage authorization.",
    ),
    "TCA-BLOCKED-USER": (
        "The user prohibition blocks the TCA task until an explicit user reversal is received.",
    ),
    "TCA-BLOCKED-RECOVERABLE": (
        "Missing local validation creates a recoverable blocker that resumes at the validation prerequisite.",
    ),
}


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
        baseline_reason, candidate_reason = STANDARD_REASONS[case_id]
        data["cases"].append(
            {
                "case_id": case_id,
                "baseline_raw": (
                    f"route={baseline[0]}\nentry_source={baseline[1]}\n"
                    f"reason={baseline_reason}"
                ),
                "candidate_raw": (
                    f"route={candidate[0]}\nentry_source={candidate[1]}\n"
                    f"reason={candidate_reason}"
                ),
                "normalized_baseline_route": baseline[0],
                "normalized_baseline_entry_source": baseline[1],
                "normalized_candidate_route": candidate[0],
                "normalized_candidate_entry_source": candidate[1],
                "pass": True,
                "hard_failure": False,
                "notes": (
                    f"{case_id} raw and normalized decisions match the accepted route expectation."
                ),
            }
        )
    for case_id, candidate in TCA.items():
        baseline = ("run", "tca-required", "active", "prohibited", "none")
        baseline_reason = TCA_BASELINE_REASONS[case_id][0]
        candidate_reason = TCA_CANDIDATE_REASONS[case_id][0]
        data["tca_cases"].append(
            {
                "case_id": case_id,
                "baseline_raw": (
                    "route=run\nentry_source=tca-required\ntask_status=active\n"
                    "next_task=prohibited\nresume_point=none\n"
                    f"reason={baseline_reason}"
                ),
                "candidate_raw": (
                    f"route={candidate[0]}\nentry_source={candidate[1]}\n"
                    f"task_status={candidate[2]}\nnext_task={candidate[3]}\n"
                    f"resume_point={candidate[4]}\n"
                    f"reason={candidate_reason}"
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
                "notes": (
                    f"{case_id} raw and normalized transition fields match the accepted expectation."
                ),
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
        self.assertTrue(any("complete case-grounded" in error for error in errors))
        self.assertTrue(any("case-specific grader" in error for error in errors))

    def test_template_delimiters_and_numeric_explanations_are_rejected(self) -> None:
        invalid_reasons = (
            "{{one substantive sentence grounded in supplied instructions}}",
            "[explain the grader disposition here]",
            "123456789012",
        )
        for reason in invalid_reasons:
            with self.subTest(reason=reason):
                data = fixture()
                data["cases"][0]["baseline_raw"] = (
                    "route=skip\nentry_source=none\n" f"reason={reason}"
                )
                errors = validate(data, verify_git=False)
                self.assertTrue(
                    any("complete case-grounded" in error for error in errors)
                )

        invalid_notes = (
            "{{explain the grader disposition here}}",
            "[explain the grader disposition here]",
            "123456789012",
        )
        for notes in invalid_notes:
            with self.subTest(notes=notes):
                data = fixture()
                data["cases"][0]["notes"] = notes
                errors = validate(data, verify_git=False)
                self.assertTrue(
                    any("case-specific grader" in error for error in errors)
                )

    def test_two_word_fragments_and_generic_reasons_are_rejected(self) -> None:
        invalid_reasons = (
            "Review warranted.",
            "Review is clearly warranted.",
            "Authentication review warranted.",
        )
        for reason in invalid_reasons:
            with self.subTest(reason=reason):
                data = fixture()
                data["cases"][0]["candidate_raw"] = (
                    "route=run\nentry_source=autonomous-risk\n" f"reason={reason}"
                )
                errors = validate(data, verify_git=False)
                self.assertTrue(
                    any("complete case-grounded" in error for error in errors)
                )

    def test_reused_canned_reasons_and_notes_are_rejected(self) -> None:
        data = fixture()
        first = data["cases"][0]
        second = data["cases"][1]
        canned = (
            "Authentication and README typo facts appear, but this identical "
            "case explanation is improperly reused."
        )
        first["baseline_raw"] = (
            "route=skip\nentry_source=none\n" f"reason={canned}"
        )
        second["baseline_raw"] = (
            "route=skip\nentry_source=none\n" f"reason={canned}"
        )
        second["notes"] = first["notes"]
        errors = validate(data, verify_git=False)
        self.assertTrue(any("reason is reused" in error for error in errors))
        self.assertTrue(any("case-specific grader" in error for error in errors))

    def test_case_grounded_korean_and_english_reasons_are_accepted(self) -> None:
        english = (
            "Authentication and concurrent failure paths make independent review necessary."
        )
        korean = "인증 토큰의 동시성 실패 경로 때문에 독립 리뷰가 필요합니다."
        self.assertTrue(reason_is_grounded("CRA-HIGH-IMPLICIT", english))
        self.assertTrue(reason_is_grounded("CRA-HIGH-IMPLICIT", korean))

    def test_candidate_prompt_fingerprint_is_bound_to_checkout(self) -> None:
        data = fixture()
        data["candidate_prompt_sha256"] = "0" * 64
        self.assertIn(
            "candidate_prompt_sha256 does not match current prompt files",
            validate(data, verify_git=False),
        )

    def test_prompt_byte_comparison_does_not_normalize_line_endings(self) -> None:
        self.assertFalse(
            prompt_bytes_equal(
                b"first line\r\nsecond line\r\n",
                b"first line\nsecond line\n",
            )
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

    def test_all_entry_sources_share_initial_invocation_ceiling(self) -> None:
        contract = (
            ROOT / "skills/software-engineering/references/cra-loop.md"
        ).read_text(encoding="utf-8")
        for text in (
            "every entry source begins with an initial effective ceiling of three",
            "ordinary configured inference usage within that initial ceiling",
            "for the same initial ceiling",
        ):
            self.assertIn(text, contract)

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
