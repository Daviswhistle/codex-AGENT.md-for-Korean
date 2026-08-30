#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
from typing import Iterable


MIN_SHORT_DESCRIPTION = 25
MAX_SHORT_DESCRIPTION = 64
_REQUIRED_INTERFACE_FIELDS = ("display_name", "short_description", "default_prompt")
_TOP_LEVEL_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*):$")
_NESTED_RE = re.compile(
    r"^  (?P<key>[A-Za-z_][A-Za-z0-9_-]*):(?: (?P<value>.*))?$"
)
_LIST_ITEM_RE = re.compile(r"^  - (?P<value>.+)$")


class OpenAIYamlContractError(ValueError):
    """Raised when an agents/openai.yaml file violates the supported contract."""


def _decode_scalar(raw: str, *, path: Path, line_number: int) -> str:
    value = raw.strip()
    if not value:
        raise OpenAIYamlContractError(f"{path}:{line_number}: scalar value is empty")
    if value in {"|", ">", "|-", ">-", "|+", ">+"}:
        raise OpenAIYamlContractError(
            f"{path}:{line_number}: block scalars are outside the supported metadata contract"
        )
    if value[0] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise OpenAIYamlContractError(
                f"{path}:{line_number}: invalid quoted scalar"
            ) from exc
        if not isinstance(parsed, str) or not parsed:
            raise OpenAIYamlContractError(
                f"{path}:{line_number}: quoted scalar must be a non-empty string"
            )
        return parsed
    return value


def validate_openai_yaml(path: Path) -> list[str]:
    """Return contract errors for one simple agents/openai.yaml metadata file."""

    path = path.resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{path}: cannot read UTF-8 metadata: {exc}"]

    errors: list[str] = []
    if "\t" in text:
        errors.append(f"{path}: tabs are not allowed")

    sections: dict[str, dict[str, str | None]] = {}
    current_section: str | None = None
    list_owner: str | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        top_match = _TOP_LEVEL_RE.fullmatch(raw_line)
        if top_match:
            current_section = top_match.group("key")
            if current_section in sections:
                errors.append(
                    f"{path}:{line_number}: duplicate top-level section {current_section!r}"
                )
            sections.setdefault(current_section, {})
            list_owner = None
            continue

        if current_section is None:
            errors.append(f"{path}:{line_number}: content appears before a top-level section")
            continue

        nested_match = _NESTED_RE.fullmatch(raw_line)
        if nested_match:
            key = nested_match.group("key")
            raw_value = nested_match.group("value")
            section = sections[current_section]
            if key in section:
                errors.append(
                    f"{path}:{line_number}: duplicate key {current_section}.{key}"
                )
            if raw_value is None or not raw_value.strip():
                section[key] = None
                list_owner = key
                continue
            try:
                section[key] = _decode_scalar(
                    raw_value, path=path, line_number=line_number
                )
            except OpenAIYamlContractError as exc:
                errors.append(str(exc))
                section[key] = ""
            list_owner = None
            continue

        list_match = _LIST_ITEM_RE.fullmatch(raw_line)
        if list_match:
            if list_owner is None:
                errors.append(f"{path}:{line_number}: list item has no owning key")
            else:
                try:
                    _decode_scalar(
                        list_match.group("value"), path=path, line_number=line_number
                    )
                except OpenAIYamlContractError as exc:
                    errors.append(str(exc))
            continue

        errors.append(
            f"{path}:{line_number}: unsupported indentation or YAML structure: {raw_line!r}"
        )

    interface = sections.get("interface")
    if interface is None:
        errors.append(f"{path}: missing top-level interface section")
        return errors

    for field in _REQUIRED_INTERFACE_FIELDS:
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}: missing non-empty interface.{field}")

    short_description = interface.get("short_description")
    if isinstance(short_description, str) and short_description:
        length = len(short_description)
        if not MIN_SHORT_DESCRIPTION <= length <= MAX_SHORT_DESCRIPTION:
            errors.append(
                f"{path}: interface.short_description must be "
                f"{MIN_SHORT_DESCRIPTION}-{MAX_SHORT_DESCRIPTION} characters "
                f"(got {length})"
            )

    return errors


def discover_openai_yaml(repo_root: Path) -> tuple[Path, ...]:
    return tuple(sorted(repo_root.glob("skills/*/agents/openai.yaml")))


def validate_paths(paths: Iterable[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        errors.extend(validate_openai_yaml(path))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the repository's agents/openai.yaml metadata contract."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="metadata files; defaults to skills/*/agents/openai.yaml",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root used when no paths are supplied",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = tuple(args.paths) or discover_openai_yaml(args.root.resolve())
    if not paths:
        print("[FAIL] no skills/*/agents/openai.yaml files found")
        return 1

    errors = validate_paths(paths)
    if errors:
        print("[FAIL] openai.yaml metadata contract")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"[PASS] openai.yaml metadata contract ({len(paths)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
