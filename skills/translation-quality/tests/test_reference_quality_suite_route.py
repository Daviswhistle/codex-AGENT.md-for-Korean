from __future__ import annotations

from pathlib import Path
import re
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
REFERENCE_SUITE = "examples/translation/good/reference-quality-suite.md"
LINK_SOURCES = (
    SKILL_ROOT / "README.md",
    SKILL_ROOT / "references" / "quality_benchmark.md",
    SKILL_ROOT / "references" / "profiles" / "report.md",
)


def linked_markdown_paths(text: str) -> set[str]:
    return set(re.findall(r"`([^`]+\.md)`", text))


class ReferenceQualitySuiteRouteTests(unittest.TestCase):
    def test_reference_quality_suite_exists_and_remains_linked(self) -> None:
        self.assertTrue((REPO_ROOT / REFERENCE_SUITE).is_file())

        for source in LINK_SOURCES:
            self.assertTrue(source.is_file(), source)
            links = linked_markdown_paths(source.read_text(encoding="utf-8"))
            self.assertIn(REFERENCE_SUITE, links, source)


if __name__ == "__main__":
    unittest.main()
