from __future__ import annotations

from pathlib import Path
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
            "The user does not need to name CRA",
            "Presume CRA is warranted when one or more of these apply:",
            "Do not use CRA as a substitute for missing local validation.",
            "Do not require the user to name CRA or ask for separate permission",
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
            "Autonomous CRA authorizes only the local commit-and-review cycle",
            cra_reference,
        )


if __name__ == "__main__":
    unittest.main()
