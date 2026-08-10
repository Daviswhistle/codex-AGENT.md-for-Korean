from __future__ import annotations

from pathlib import Path
import re
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL = SKILL_ROOT / "SKILL.md"
PUBLISHABLE_PROFILE = "references/publishable-html-article.md"
READER_FIRST_EXAMPLES = "references/reader-first-information-design-examples.md"


def markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    start = text.index(marker) + len(marker)
    next_heading = re.search(r"^## ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def referenced_markdown_paths(text: str) -> set[str]:
    return set(re.findall(r"`(references/[^`]+\.md)`", text))


class WritingResourceRouteTests(unittest.TestCase):
    def test_publishable_article_profile_is_linked_from_call_boundary(self) -> None:
        call_boundary = markdown_section(
            SKILL.read_text(encoding="utf-8"),
            "호출 경계",
        )
        routed_references = referenced_markdown_paths(call_boundary)

        self.assertIn(PUBLISHABLE_PROFILE, routed_references)
        self.assertTrue((SKILL_ROOT / PUBLISHABLE_PROFILE).is_file())

    def test_reader_first_examples_are_linked_from_reference_map(self) -> None:
        reference_map = markdown_section(
            SKILL.read_text(encoding="utf-8"),
            "참고 자료",
        )
        mapped_references = referenced_markdown_paths(reference_map)

        self.assertIn(READER_FIRST_EXAMPLES, mapped_references)
        self.assertTrue((SKILL_ROOT / READER_FIRST_EXAMPLES).is_file())


if __name__ == "__main__":
    unittest.main()
