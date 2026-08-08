from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class CraAutonomyContractTests(unittest.TestCase):
    def test_cra_can_be_selected_without_an_explicit_request(self) -> None:
        skill = read("skills/software-engineering/SKILL.md")
        cra = read("skills/software-engineering/references/cra-loop.md")

        self.assertIn("The user does not need to name CRA.", skill)
        self.assertIn("When the CRA decision says to run", skill)
        self.assertIn(
            "or the software-engineering skill selects CRA autonomously.",
            cra,
        )
        self.assertIn("`autonomous-risk`", cra)
        self.assertNotIn(
            "Use only when the user explicitly requests `CRA 루프`.",
            skill,
        )

    def test_autonomous_cra_keeps_existing_authority_boundaries(self) -> None:
        skill = read("skills/software-engineering/SKILL.md")
        cra = read("skills/software-engineering/references/cra-loop.md")

        self.assertIn(
            "Autonomous CRA selection does not authorize starting TCA.",
            skill,
        )
        self.assertIn(
            "Use only when the user explicitly requests `TCA 루프`.",
            skill,
        )
        self.assertIn(
            "already-configured reviewer and the current account's existing usage",
            skill,
        )
        self.assertIn("It does not authorize purchasing credits", skill)
        self.assertIn(
            "A local commit is not approval to push, deploy, migrate",
            cra,
        )


if __name__ == "__main__":
    unittest.main()
