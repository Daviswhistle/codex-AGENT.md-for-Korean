from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


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

    def test_routing_evaluation_covers_representative_behavior(self) -> None:
        evaluation = read(
            "skills/software-engineering/references/cra-routing-evaluation.md"
        )
        references_index = read("skills/software-engineering/references/README.md")

        self.assertIn("cra-routing-evaluation.md", references_index)
        for case_id in (
            "CRA-HIGH-IMPLICIT",
            "CRA-LOW-IMPLICIT",
            "CRA-LOW-EXPLICIT",
            "CRA-LOW-TCA",
            "CRA-HIGH-USER-BLOCK",
            "CRA-HIGH-PURCHASE",
            "CRA-HIGH-FOURTH-RUN",
        ):
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
            "They do not replace the isolated behavior run.",
        ):
            self.assertIn(statement, evaluation)

    def test_completed_routing_evaluation_record_exists_before_merge(self) -> None:
        record_path = (
            ROOT
            / "skills"
            / "software-engineering"
            / "evals"
            / "cra-autonomous-routing-v1.md"
        )
        self.assertTrue(
            record_path.is_file(),
            "CRA routing behavior evaluation is required before merge: "
            "run the isolated baseline/candidate matrix and write "
            "skills/software-engineering/evals/cra-autonomous-routing-v1.md",
        )

        record = record_path.read_text(encoding="utf-8")
        for field in (
            "evaluation_id: cra-autonomous-routing-v1",
            "status: completed",
            "model:",
            "reasoning_effort:",
            "tool_availability:",
            "evaluator_prompt_version: v1",
        ):
            self.assertIn(field, record)

        for commit_field in ("baseline_commit", "candidate_commit"):
            self.assertRegex(
                record,
                rf"(?m)^{commit_field}: [0-9a-f]{{40}}$",
            )

        case_ids = (
            "CRA-HIGH-IMPLICIT",
            "CRA-LOW-IMPLICIT",
            "CRA-LOW-EXPLICIT",
            "CRA-LOW-TCA",
            "CRA-HIGH-USER-BLOCK",
            "CRA-HIGH-PURCHASE",
            "CRA-HIGH-FOURTH-RUN",
        )
        for case_id in case_ids:
            self.assertEqual(record.count(f"case_id: {case_id}"), 1)

        self.assertGreaterEqual(record.count("baseline_raw:"), len(case_ids))
        self.assertGreaterEqual(record.count("candidate_raw:"), len(case_ids))
        self.assertGreaterEqual(record.count("pass: true"), len(case_ids))
        self.assertNotIn("status: pending", record)
        self.assertNotIn("pass: false", record)
        self.assertNotIn("hard_failure: true", record)

        sha_pattern = re.compile(r"^[0-9a-f]{40}$")
        for field in ("baseline_commit", "candidate_commit"):
            value = next(
                line.split(":", 1)[1].strip()
                for line in record.splitlines()
                if line.startswith(f"{field}:")
            )
            self.assertRegex(value, sha_pattern)


if __name__ == "__main__":
    unittest.main()
