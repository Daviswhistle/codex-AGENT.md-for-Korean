from __future__ import annotations

from pathlib import Path
import re
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = SKILL_ROOT / "SKILL.md"
PUBLISHABLE_PROFILE = "references/publishable-html-article.md"


def markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    start = text.index(marker) + len(marker)
    next_heading = re.search(r"^## ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


class PublishableArticleRouteTests(unittest.TestCase):
    def test_publishable_article_profile_is_linked_from_call_boundary(self) -> None:
        call_boundary = markdown_section(
            SKILL.read_text(encoding="utf-8"),
            "호출 경계",
        )
        routed_references = set(
            re.findall(r"`(references/[^`]+\.md)`", call_boundary)
        )

        self.assertIn(PUBLISHABLE_PROFILE, routed_references)
        self.assertTrue((SKILL_ROOT / PUBLISHABLE_PROFILE).is_file())


if __name__ == "__main__":
    unittest.main()
