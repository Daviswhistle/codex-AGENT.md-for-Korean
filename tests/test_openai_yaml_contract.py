from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.openai_yaml_contract import validate_openai_yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def metadata(short_description: str, *, include_default_prompt: bool = True) -> str:
    lines = [
        "interface:",
        '  display_name: "Writing Quality"',
        f'  short_description: "{short_description}"',
    ]
    if include_default_prompt:
        lines.append('  default_prompt: "Use $writing-quality for this text."')
    return "\n".join(lines) + "\n"


class OpenAIYamlContractTests(unittest.TestCase):
    def validate_text(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "openai.yaml"
            path.write_text(text, encoding="utf-8")
            return validate_openai_yaml(path)

    def test_repository_metadata_files_satisfy_contract(self) -> None:
        paths = sorted(REPO_ROOT.glob("skills/*/agents/openai.yaml"))
        self.assertTrue(paths)
        errors = [error for path in paths for error in validate_openai_yaml(path)]
        self.assertEqual([], errors)

    def test_short_description_accepts_inclusive_boundaries(self) -> None:
        self.assertEqual([], self.validate_text(metadata("a" * 25)))
        self.assertEqual([], self.validate_text(metadata("b" * 64)))

    def test_short_description_rejects_out_of_range_values(self) -> None:
        too_short = self.validate_text(metadata("a" * 24))
        too_long = self.validate_text(metadata("b" * 65))
        reviewed_value = self.validate_text(
            metadata("Draft and review polished user-facing text and evidence-backed research")
        )
        self.assertTrue(any("got 24" in error for error in too_short))
        self.assertTrue(any("got 65" in error for error in too_long))
        self.assertTrue(any("got 71" in error for error in reviewed_value))

    def test_required_interface_field_is_enforced(self) -> None:
        errors = self.validate_text(
            metadata("A valid metadata description", include_default_prompt=False)
        )
        self.assertTrue(any("interface.default_prompt" in error for error in errors))

    def test_malformed_indentation_is_rejected(self) -> None:
        errors = self.validate_text(
            "interface:\n   display_name: Wrong indentation\n"
            "  short_description: A valid metadata description\n"
            "  default_prompt: Use $writing-quality.\n"
        )
        self.assertTrue(any("unsupported indentation" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
