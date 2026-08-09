from __future__ import annotations

from pathlib import Path
import re
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = SKILL_ROOT / "SKILL.md"


def markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    start = text.index(marker) + len(marker)
    next_heading = re.search(r"^## ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


class StagedRoutingContractTests(unittest.TestCase):
    def test_required_loading_routes_are_declared_in_staged_section(self) -> None:
        staged = markdown_section(
            SKILL.read_text(encoding="utf-8"),
            "Staged Reference Loading",
        )

        routes = set(
            re.findall(r"^\s*-\s+Use\s+`([^`]+)`", staged, re.MULTILINE)
        )
        self.assertEqual(
            routes,
            {
                "core-only",
                "references/profiles/transcript.md",
                "references/profiles/report.md",
            },
        )

        required_resources = {
            "references/core.md",
            "references/terminology.md",
            "references/profiles/transcript.md",
            "references/profiles/report.md",
            "references/quality_benchmark.md",
        }
        staged_resources = set(
            re.findall(r"`((?:references|agents|scripts)/[^`]+)`", staged)
        )
        self.assertTrue(
            required_resources.issubset(staged_resources),
            required_resources - staged_resources,
        )

        for relative_path in required_resources:
            self.assertTrue((SKILL_ROOT / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
