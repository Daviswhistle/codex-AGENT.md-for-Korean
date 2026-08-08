from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
TERMINOLOGY = ROOT / "references" / "terminology.md"


class TerminologyContractTests(unittest.TestCase):
    def test_skill_loads_source_wide_terminology_contract(self) -> None:
        skill_text = SKILL.read_text(encoding="utf-8")
        terminology_text = TERMINOLOGY.read_text(encoding="utf-8")
        text = "\n".join((skill_text, terminology_text))

        self.assertTrue(TERMINOLOGY.is_file())
        self.assertLessEqual(len(skill_text.splitlines()), 120)

        required_phrases = [
            "references/terminology.md",
            "source-wide terminology ledger",
            "aliases, former names",
            "established Korean rendering",
            "Do not mix source spelling and Korean transliteration arbitrarily",
            "naming-class consistency",
            "later passage proves that two names identify the same entity",
            "revise the first occurrence",
            "Scan the entire source before translating substantive chunks",
            "source-derived",
            "officially verified",
            "not as a blind rule that every drug name must be transliterated",
            "카그리세마(CagriSema)",
            "제나감타이드(zenagamtide·구 아미크레틴)",
            "This example is not a universal rule that all medicine names must be written in Korean",
            "Treat identity confusion or a false alias as P1",
            "Treat arbitrary naming-class drift, a missing useful former name, or delayed alias disclosure as P2",
            "compare the final output against the terminology ledger occurrence by occurrence",
        ]
        missing = [phrase for phrase in required_phrases if phrase not in text]
        self.assertEqual(missing, [])

    def test_alias_discovery_must_back_propagate(self) -> None:
        text = TERMINOLOGY.read_text(encoding="utf-8")
        later = text.index("later proves that two names refer to the same entity")
        revise = text.index("revise the first occurrence", later)
        self.assertGreater(revise, later)
        self.assertIn("Earlier chunks must be revised", text)
        self.assertIn("back-propagation of a later alias discovery", text)


if __name__ == "__main__":
    unittest.main()
