from __future__ import annotations

from pathlib import Path
import re
import shlex
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPORT_PROFILE = SKILL_ROOT / "references" / "profiles" / "report.md"
SHELL_FENCE = re.compile(r"```(?:bash|sh|shell)\n(.*?)```", re.DOTALL)


def logical_shell_commands(block: str) -> list[str]:
    commands: list[str] = []
    current: list[str] = []

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            current.append(line[:-1].rstrip())
            continue

        current.append(line)
        commands.append(" ".join(current))
        current = []

    if current:
        commands.append(" ".join(current))

    return commands


def has_option(tokens: list[str], option: str, value: str) -> bool:
    if f"{option}={value}" in tokens:
        return True
    return any(
        token == option and index + 1 < len(tokens) and tokens[index + 1] == value
        for index, token in enumerate(tokens)
    )


class ReportProfileCommandTests(unittest.TestCase):
    def test_report_qa_command_selects_report_profile(self) -> None:
        text = REPORT_PROFILE.read_text(encoding="utf-8")
        qa_commands: list[list[str]] = []

        for block in SHELL_FENCE.findall(text):
            for command in logical_shell_commands(block):
                tokens = shlex.split(command)
                if any(token.endswith("qa_html_translation.py") for token in tokens):
                    qa_commands.append(tokens)

        self.assertTrue(qa_commands, "report profile must declare a QA helper command")
        self.assertTrue(
            any(has_option(tokens, "--profile", "report") for tokens in qa_commands),
            "formal-report QA command must pass --profile report",
        )


if __name__ == "__main__":
    unittest.main()
