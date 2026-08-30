#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlparse


MIN_SHORT_DESCRIPTION = 25
MAX_SHORT_DESCRIPTION = 64
_REQUIRED_INTERFACE_FIELDS = ("display_name", "short_description", "default_prompt")
_KEY_VALUE_RE = re.compile(
    r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*):(?: (?P<value>.*))?$"
)
_ALLOWED_MCP_FIELDS = {"type", "value", "description", "transport", "url"}
_REQUIRED_MCP_FIELDS = ("type", "value")


class OpenAIYamlContractError(ValueError):
    """Raised when an agents/openai.yaml file violates the supported contract."""


@dataclass(frozen=True)
class _YamlLine:
    line_number: int
    indent: int
    text: str


def _decode_scalar(raw: str, *, path: Path, line_number: int) -> Any:
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

    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    return value


def _tokenize_yaml(text: str, *, path: Path) -> list[_YamlLine]:
    if "\t" in text:
        raise OpenAIYamlContractError(f"{path}: tabs are not allowed")

    tokens: list[_YamlLine] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent % 2:
            raise OpenAIYamlContractError(
                f"{path}:{line_number}: unsupported indentation; use multiples of two spaces"
            )
        tokens.append(
            _YamlLine(line_number=line_number, indent=indent, text=raw_line[indent:])
        )
    return tokens


def _parse_mapping(
    tokens: list[_YamlLine], index: int, indent: int, *, path: Path
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(tokens):
        token = tokens[index]
        if token.indent < indent:
            break
        if token.indent > indent:
            raise OpenAIYamlContractError(
                f"{path}:{token.line_number}: unsupported indentation or YAML structure"
            )
        if token.text.startswith("- "):
            break

        match = _KEY_VALUE_RE.fullmatch(token.text)
        if match is None:
            raise OpenAIYamlContractError(
                f"{path}:{token.line_number}: expected an unquoted mapping key"
            )
        key = match.group("key")
        if key in result:
            raise OpenAIYamlContractError(
                f"{path}:{token.line_number}: duplicate key {key!r}"
            )

        raw_value = match.group("value")
        index += 1
        if raw_value is not None and raw_value.strip():
            result[key] = _decode_scalar(
                raw_value, path=path, line_number=token.line_number
            )
            continue

        if index >= len(tokens):
            result[key] = {}
            continue

        next_token = tokens[index]
        if next_token.indent == indent and next_token.text.startswith("- "):
            # YAML permits an indentationless sequence as a mapping value.
            result[key], index = _parse_list(tokens, index, indent, path=path)
        elif next_token.indent == indent + 2:
            result[key], index = _parse_block(tokens, index, indent + 2, path=path)
        elif next_token.indent <= indent:
            result[key] = {}
        else:
            raise OpenAIYamlContractError(
                f"{path}:{next_token.line_number}: unsupported indentation or YAML structure"
            )
    return result, index


def _parse_list(
    tokens: list[_YamlLine], index: int, indent: int, *, path: Path
) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(tokens):
        token = tokens[index]
        if token.indent < indent:
            break
        if token.indent > indent:
            raise OpenAIYamlContractError(
                f"{path}:{token.line_number}: unsupported indentation or YAML structure"
            )
        if not token.text.startswith("- "):
            break

        item_text = token.text[2:].strip()
        index += 1
        if not item_text:
            if index >= len(tokens) or tokens[index].indent != indent + 2:
                raise OpenAIYamlContractError(
                    f"{path}:{token.line_number}: empty list item needs a nested value"
                )
            item, index = _parse_block(tokens, index, indent + 2, path=path)
            result.append(item)
            continue

        mapping_match = _KEY_VALUE_RE.fullmatch(item_text)
        if mapping_match is None:
            result.append(
                _decode_scalar(item_text, path=path, line_number=token.line_number)
            )
            continue

        key = mapping_match.group("key")
        raw_value = mapping_match.group("value")
        item_mapping: dict[str, Any] = {}
        if raw_value is not None and raw_value.strip():
            item_mapping[key] = _decode_scalar(
                raw_value, path=path, line_number=token.line_number
            )
        elif index < len(tokens) and tokens[index].indent == indent + 2:
            item_mapping[key], index = _parse_block(
                tokens, index, indent + 2, path=path
            )
        else:
            item_mapping[key] = {}

        if index < len(tokens) and tokens[index].indent == indent + 2:
            continuation, index = _parse_mapping(
                tokens, index, indent + 2, path=path
            )
            duplicates = sorted(set(item_mapping) & set(continuation))
            if duplicates:
                raise OpenAIYamlContractError(
                    f"{path}:{tokens[index - 1].line_number}: duplicate list-item key "
                    f"{duplicates[0]!r}"
                )
            item_mapping.update(continuation)
        result.append(item_mapping)
    return result, index


def _parse_block(
    tokens: list[_YamlLine], index: int, indent: int, *, path: Path
) -> tuple[Any, int]:
    if index >= len(tokens):
        return {}, index
    token = tokens[index]
    if token.indent != indent:
        raise OpenAIYamlContractError(
            f"{path}:{token.line_number}: unsupported indentation or YAML structure"
        )
    if token.text.startswith("- "):
        return _parse_list(tokens, index, indent, path=path)
    return _parse_mapping(tokens, index, indent, path=path)


def _parse_yaml_subset(text: str, *, path: Path) -> dict[str, Any]:
    tokens = _tokenize_yaml(text, path=path)
    if not tokens:
        raise OpenAIYamlContractError(f"{path}: metadata file is empty")
    if tokens[0].indent != 0 or tokens[0].text.startswith("- "):
        raise OpenAIYamlContractError(f"{path}: top level must be a mapping")
    parsed, index = _parse_mapping(tokens, 0, 0, path=path)
    if index != len(tokens):
        token = tokens[index]
        raise OpenAIYamlContractError(
            f"{path}:{token.line_number}: unsupported indentation or YAML structure"
        )
    return parsed


def _validate_mcp_dependencies(
    root: dict[str, Any], *, path: Path, errors: list[str]
) -> None:
    dependencies = root.get("dependencies")
    if dependencies is None:
        return
    if not isinstance(dependencies, dict):
        errors.append(f"{path}: dependencies must be a mapping")
        return

    unknown_dependency_keys = sorted(set(dependencies) - {"tools"})
    for key in unknown_dependency_keys:
        errors.append(f"{path}: unsupported dependencies key {key!r}")

    tools = dependencies.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append(f"{path}: dependencies.tools must be a non-empty list")
        return

    for index, tool in enumerate(tools):
        prefix = f"{path}: dependencies.tools[{index}]"
        if not isinstance(tool, dict):
            errors.append(f"{prefix} must be a mapping")
            continue

        unknown_fields = sorted(set(tool) - _ALLOWED_MCP_FIELDS)
        for field in unknown_fields:
            errors.append(f"{prefix} has unsupported field {field!r}")

        for field in _REQUIRED_MCP_FIELDS:
            value = tool.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")

        tool_type = tool.get("type")
        if isinstance(tool_type, str) and tool_type != "mcp":
            errors.append(f"{prefix}.type only supports 'mcp' (got {tool_type!r})")

        for field in ("description", "transport", "url"):
            value = tool.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f"{prefix}.{field} must be a non-empty string when present")

        url = tool.get("url")
        if isinstance(url, str) and url:
            parsed_url = urlparse(url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                errors.append(f"{prefix}.url must be an absolute HTTP(S) URL")


def validate_openai_yaml(path: Path) -> list[str]:
    """Return contract errors for one agents/openai.yaml metadata file."""

    path = path.resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{path}: cannot read UTF-8 metadata: {exc}"]

    try:
        root = _parse_yaml_subset(text, path=path)
    except OpenAIYamlContractError as exc:
        return [str(exc)]

    errors: list[str] = []
    interface = root.get("interface")
    if not isinstance(interface, dict):
        errors.append(f"{path}: missing top-level interface mapping")
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

    _validate_mcp_dependencies(root, path=path, errors=errors)
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
