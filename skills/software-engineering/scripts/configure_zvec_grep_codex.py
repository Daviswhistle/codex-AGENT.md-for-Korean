#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import tomllib


START_MARKER = "# ZVEC_GREP_START"
END_MARKER = "# ZVEC_GREP_END"
DEFAULT_TOOL_TIMEOUT_SEC = 600
MANAGED_ZVEC_KEYS = {
    "command",
    "args",
    "tool_timeout_sec",
    "default_tools_approval_mode",
}


class ConfigError(RuntimeError):
    """Raised when the Codex configuration cannot be changed safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Configure only the zvec-grep MCP entry in Codex. "
            "This helper never edits AGENTS.md."
        )
    )
    parser.add_argument(
        "action",
        choices=("install", "check", "uninstall"),
        help="install or check the managed MCP block, or uninstall only that block",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME") or "~/.codex"),
        help="Codex home (default: CODEX_HOME or ~/.codex)",
    )
    parser.add_argument(
        "--zg-command",
        default="zg",
        help="zvec-grep executable or absolute path (default: zg)",
    )
    parser.add_argument(
        "--tool-timeout-sec",
        type=int,
        default=DEFAULT_TOOL_TIMEOUT_SEC,
        help=f"Codex MCP tool timeout (default: {DEFAULT_TOOL_TIMEOUT_SEC})",
    )
    parser.add_argument(
        "--skip-command-check",
        action="store_true",
        help="install or check without requiring zg on the current PATH",
    )
    return parser.parse_args(argv)


def _toml_string(value: str) -> str:
    # TOML basic strings use the same escaping needed here as JSON strings.
    return json.dumps(value, ensure_ascii=False)


def render_block(zg_command: str, tool_timeout_sec: int) -> str:
    if tool_timeout_sec <= 0:
        raise ConfigError("tool timeout must be a positive integer")
    return "\n".join(
        (
            START_MARKER,
            "[mcp_servers.zvec_grep]",
            f"command = {_toml_string(zg_command)}",
            'args = ["server", "--stdio", "--mcp-toolset", "agent"]',
            f"tool_timeout_sec = {tool_timeout_sec}",
            'default_tools_approval_mode = "approve"',
            END_MARKER,
        )
    )


def _marker_bounds(lines: list[str]) -> tuple[int, int] | None:
    starts = [index for index, line in enumerate(lines) if line.strip() == START_MARKER]
    ends = [index for index, line in enumerate(lines) if line.strip() == END_MARKER]
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ConfigError(
            "malformed or duplicated zvec-grep markers in config.toml; inspect them manually"
        )
    return starts[0], ends[0]


def _without_managed_block(
    lines: list[str],
    bounds: tuple[int, int] | None,
) -> str:
    if bounds is None:
        return "\n".join(lines)
    start, end = bounds
    return "\n".join([*lines[:start], *lines[end + 1 :]])


def _parse_toml(source: str, context: str) -> dict[str, object]:
    if not source.strip():
        return {}
    try:
        return tomllib.loads(source)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{context} is not valid TOML: {exc}") from exc


def _assert_no_unmanaged_config(
    lines: list[str],
    bounds: tuple[int, int] | None,
) -> None:
    unmanaged = _parse_toml(
        _without_managed_block(lines, bounds),
        "config.toml outside the managed zvec-grep block",
    )
    mcp_servers = unmanaged.get("mcp_servers")
    if isinstance(mcp_servers, dict) and "zvec_grep" in mcp_servers:
        raise ConfigError(
            "unmanaged mcp_servers.zvec_grep configuration already exists; "
            "inspect it manually instead of overwriting it"
        )


def _zvec_config(parsed: dict[str, object]) -> object | None:
    mcp_servers = parsed.get("mcp_servers")
    if not isinstance(mcp_servers, dict):
        return None
    return mcp_servers.get("zvec_grep")


def _assert_managed_config_is_complete(
    source: str,
    lines: list[str],
    bounds: tuple[int, int] | None,
) -> None:
    if bounds is None:
        return

    start, end = bounds
    full_config = _parse_toml(source, "config.toml")
    managed_config = _parse_toml(
        "\n".join(lines[start : end + 1]),
        "managed zvec-grep block",
    )
    managed_mcp_servers = managed_config.get("mcp_servers")
    if (
        set(managed_config) != {"mcp_servers"}
        or not isinstance(managed_mcp_servers, dict)
        or set(managed_mcp_servers) != {"zvec_grep"}
    ):
        raise ConfigError(
            "managed zvec-grep markers contain unrelated TOML; move every "
            "other key or table outside the markers"
        )

    full_zvec = _zvec_config(full_config)
    managed_zvec = _zvec_config(managed_config)
    if not isinstance(managed_zvec, dict):
        raise ConfigError("managed zvec-grep block must define a TOML table")
    unexpected_keys = set(managed_zvec) - MANAGED_ZVEC_KEYS
    if unexpected_keys:
        names = ", ".join(sorted(unexpected_keys))
        raise ConfigError(
            "managed zvec-grep markers contain unsupported keys or nested "
            f"tables: {names}"
        )
    if full_zvec != managed_zvec:
        raise ConfigError(
            "managed markers do not enclose the entire "
            "mcp_servers.zvec_grep configuration; inspect adjacent keys or "
            "nested tables manually"
        )


def _validate_result(source: str) -> None:
    _parse_toml(source, "resulting config.toml")


def install_source(source: str, zg_command: str, tool_timeout_sec: int) -> str:
    block = render_block(zg_command, tool_timeout_sec)
    lines = source.splitlines()
    bounds = _marker_bounds(lines)
    _assert_no_unmanaged_config(lines, bounds)
    _assert_managed_config_is_complete(source, lines, bounds)

    if bounds is None:
        prefix = source.rstrip()
        updated = f"{prefix}\n\n{block}\n" if prefix else f"{block}\n"
        _validate_result(updated)
        return updated

    start, end = bounds
    next_lines = [*lines[:start], *block.splitlines(), *lines[end + 1 :]]
    updated = "\n".join(next_lines).rstrip() + "\n"
    _validate_result(updated)
    return updated


def uninstall_source(source: str) -> str:
    lines = source.splitlines()
    bounds = _marker_bounds(lines)
    _assert_no_unmanaged_config(lines, bounds)
    _assert_managed_config_is_complete(source, lines, bounds)
    if bounds is None:
        return source

    start, end = bounds
    before = "\n".join(lines[:start]).rstrip()
    after = "\n".join(lines[end + 1 :]).lstrip("\n")
    retained = [part for part in (before, after) if part]
    updated = ("\n\n".join(retained).rstrip() + "\n") if retained else ""
    _validate_result(updated)
    return updated


def check_source(source: str, zg_command: str, tool_timeout_sec: int) -> None:
    lines = source.splitlines()
    bounds = _marker_bounds(lines)
    _assert_no_unmanaged_config(lines, bounds)
    _assert_managed_config_is_complete(source, lines, bounds)
    if bounds is None:
        raise ConfigError("managed zvec-grep MCP block is missing")

    start, end = bounds
    actual = "\n".join(lines[start : end + 1]).strip()
    expected = render_block(zg_command, tool_timeout_sec).strip()
    if actual != expected:
        raise ConfigError(
            "managed zvec-grep MCP block differs from the requested configuration; "
            "rerun the install action"
        )
    _validate_result(source)


def _resolve_write_target(path: Path, visited: set[Path] | None = None) -> Path:
    absolute = Path(os.path.abspath(path))
    seen = visited if visited is not None else set()
    if absolute in seen:
        raise ConfigError(f"circular symbolic link while resolving {path}")

    try:
        link_target = absolute.readlink()
    except FileNotFoundError:
        return absolute
    except OSError:
        if not absolute.is_symlink():
            return absolute
        raise

    seen.add(absolute)
    if not link_target.is_absolute():
        link_target = absolute.parent / link_target
    return _resolve_write_target(link_target, seen)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write_text_atomic(path: Path, content: str) -> None:
    target = _resolve_write_target(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    mode = 0o600
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        pass

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, target)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _has_path_component(command: str) -> bool:
    path = Path(command)
    separators = {os.sep, os.altsep, "/", "\\"}
    return (
        path.is_absolute()
        or bool(path.drive)
        or command.startswith("~")
        or any(separator and separator in command for separator in separators)
    )


def normalize_command(command: str) -> str:
    if not command:
        raise ConfigError("zvec-grep executable must not be empty")
    if not _has_path_component(command):
        return command

    try:
        candidate = Path(command).expanduser()
    except RuntimeError as exc:
        raise ConfigError(f"cannot expand zvec-grep executable path: {command}") from exc
    return str(Path(os.path.abspath(candidate)))


def _command_available(command: str) -> bool:
    if _has_path_component(command):
        candidate = Path(command)
        return candidate.is_file() and os.access(candidate, os.X_OK)
    return shutil.which(command) is not None


def require_command(command: str) -> None:
    if not _command_available(command):
        raise ConfigError(
            f"zvec-grep executable not found: {command}. "
            "Install @zvec/zvec-grep first or pass --skip-command-check deliberately."
        )


def install_config(config_path: Path, zg_command: str, tool_timeout_sec: int) -> bool:
    source = _read_text(config_path)
    updated = install_source(source, zg_command, tool_timeout_sec)
    if updated == source:
        return False
    _write_text_atomic(config_path, updated)
    return True


def uninstall_config(config_path: Path) -> bool:
    source = _read_text(config_path)
    updated = uninstall_source(source)
    if updated == source:
        return False
    _write_text_atomic(config_path, updated)
    return True


def check_config(config_path: Path, zg_command: str, tool_timeout_sec: int) -> None:
    source = _read_text(config_path)
    check_source(source, zg_command, tool_timeout_sec)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        codex_home = Path(os.path.abspath(args.codex_home.expanduser()))
        config_path = codex_home / "config.toml"
        zg_command = args.zg_command

        if args.action in {"install", "check"}:
            zg_command = normalize_command(args.zg_command)
            if not args.skip_command_check:
                require_command(zg_command)

        if args.action == "install":
            changed = install_config(
                config_path,
                zg_command,
                args.tool_timeout_sec,
            )
            verb = "WRITE" if changed else "KEEP"
            print(f"{verb} {config_path}")
            print("zvec-grep MCP config is ready; AGENTS.md was not modified.")
        elif args.action == "check":
            check_config(config_path, zg_command, args.tool_timeout_sec)
            print(f"PASS {config_path}")
        else:
            changed = uninstall_config(config_path)
            verb = "REMOVE" if changed else "KEEP"
            print(f"{verb} {config_path}")
    except (ConfigError, OSError, UnicodeError) as exc:
        print(f"zvec-grep Codex configuration failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
