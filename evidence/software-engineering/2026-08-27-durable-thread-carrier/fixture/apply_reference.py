\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
args = parser.parse_args()
repo = Path(args.repo).resolve()

(repo / "src/labels.py").write_text(
    '''def normalize_label(value: str) -> str:\n    \"\"\"Collapse surrounding and repeated whitespace in one label.\"\"\"\n    return \" \".join(value.split())\n\n\ndef dedupe_labels(values: list[str]) -> list[str]:\n    \"\"\"Return first normalized spellings, compared case-insensitively.\"\"\"\n    seen: set[str] = set()\n    result: list[str] = []\n    for value in values:\n        normalized = normalize_label(value)\n        if not normalized:\n            continue\n        key = normalized.casefold()\n        if key in seen:\n            continue\n        seen.add(key)\n        result.append(normalized)\n    return result\n''',
    encoding="utf-8",
)
(repo / "tests/test_labels.py").write_text(
    '''import unittest\n\nfrom src.labels import dedupe_labels, normalize_label\n\n\nclass NormalizeLabelTests(unittest.TestCase):\n    def test_collapses_whitespace(self) -> None:\n        self.assertEqual(normalize_label(\"  Alpha   Beta  \"), \"Alpha Beta\")\n\n\nclass DedupeLabelsTests(unittest.TestCase):\n    def test_normalizes_drops_empty_and_preserves_first_spelling(self) -> None:\n        self.assertEqual(\n            dedupe_labels([\" Alpha \", \"alpha\", \"  \", \"Beta\", \" BETA \", \"Gamma\"]),\n            [\"Alpha\", \"Beta\", \"Gamma\"],\n        )\n\n    def test_uses_casefold(self) -> None:\n        self.assertEqual(dedupe_labels([\"Straße\", \"STRASSE\"]), [\"Straße\"])\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n''',
    encoding="utf-8",
)
