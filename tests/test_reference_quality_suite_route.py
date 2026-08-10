from __future__ import annotations

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SUITE = "examples/translation/good/reference-quality-suite.md"
LINK_SOURCES = (
    REPO_ROOT / "skills" / "translation-quality" / "README.md",
    REPO_ROOT
    / "skills"
    / "translation-quality"
    / "references"
    / "quality_benchmark.md",
    REPO_ROOT
    / "skills"
    / "translation-quality"
    / "references"
    / "profiles"
    / "report.md",
)


def linked_markdown_paths(text: str) -> set[str]:
    return set(re.findall(r"`([^`]+\.md)`", text))


class ReferenceQualitySuiteRouteTests(unittest.TestCase):
    def test_repository_reference_suite_exists_and_remains_linked(self) -> None:
        self.assertTrue((REPO_ROOT / REFERENCE_SUITE).is_file())

        for source in LINK_SOURCES:
            self.assertTrue(source.is_file(), source)
            links = linked_markdown_paths(source.read_text(encoding="utf-8"))
            self.assertIn(REFERENCE_SUITE, links, source)


if __name__ == "__main__":
    unittest.main()
