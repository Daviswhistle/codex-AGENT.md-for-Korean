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


def numbered_item_child_bullets(text: str) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] | None = None

    for line in text.splitlines():
        if re.match(r"^\d+\.\s+", line):
            current = []
            groups.append(current)
            continue

        if current is None:
            continue

        child = re.match(r"^\s+-\s+(.+)$", line)
        if child:
            current.append(child.group(1))

    return groups


class StagedRoutingContractTests(unittest.TestCase):
    def test_required_loading_routes_are_declared_in_staged_section(self) -> None:
        staged = markdown_section(
            SKILL.read_text(encoding="utf-8"),
            "Staged Reference Loading",
        )

        required_routes = {
            "core-only",
            "references/profiles/transcript.md",
            "references/profiles/report.md",
        }
        route_group_found = False

        for bullets in numbered_item_child_bullets(staged):
            declared: dict[str, str] = {}
            valid_group = True

            for bullet in bullets:
                tokens = set(re.findall(r"`([^`]+)`", bullet)) & required_routes
                if len(tokens) > 1:
                    valid_group = False
                    break
                if len(tokens) == 1:
                    route = next(iter(tokens))
                    if route in declared:
                        valid_group = False
                        break
                    declared[route] = bullet

            if valid_group and set(declared) == required_routes:
                route_group_found = True
                break

        self.assertTrue(
            route_group_found,
            "core-only, transcript, and report must each have a distinct child route entry",
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
