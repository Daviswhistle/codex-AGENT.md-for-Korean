#!/usr/bin/env python3
"""Durable local control-state ledger for outcome ownership."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
from datetime import UTC, datetime
import errno
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import struct
import sys
import tempfile
import time
from typing import Any, Callable, Iterator
import uuid


MISSION_STATES = (
    "active",
    "waiting",
    "blocked",
    "verifying",
    "interrupted",
    "complete",
    "abandoned",
)
TERMINAL_STATES = frozenset({"complete", "abandoned"})
LEASE_RELEASING_STATES = frozenset(
    {"waiting", "blocked", "interrupted", "complete", "abandoned"}
)
EVENT_KINDS = (
    "checkpoint",
    "progress",
    "decision",
    "evidence",
    "risk",
    "blocker",
    "opportunity",
    "recovery",
)
REPO_CREATION_KIND_PRIORITY = (
    "linux-file-handle",
    "filesystem-generation",
    "linux-statx-birth-time",
    "filesystem-birth-time-ns",
    "windows-creation-time-ns",
)
REPO_CREATION_KINDS = frozenset(REPO_CREATION_KIND_PRIORITY)
ALLOWED_TRANSITIONS = {
    "active": frozenset(
        {"waiting", "blocked", "verifying", "interrupted", "abandoned"}
    ),
    "waiting": frozenset({"active", "abandoned"}),
    "blocked": frozenset({"active", "waiting", "abandoned"}),
    "verifying": frozenset({"active", "blocked", "interrupted", "complete"}),
    "interrupted": frozenset({"active", "abandoned"}),
    "complete": frozenset(),
    "abandoned": frozenset(),
}
DEFAULT_TTL_SECONDS = 900.0
DEFAULT_EVENTS_LIMIT = 100
DEFAULT_LIST_LIMIT = 100
SQLITE_INT64_MAX = (1 << 63) - 1
SCHEMA_VERSION = 1
APPLICATION_ID = 0x4F574E52  # ASCII "OWNR"
REQUIRED_TABLES = frozenset({"missions", "events", "leases"})
SQLITE_HEADER_MAGIC = b"SQLite format 3\x00"
SQLITE_HEADER_SIZE = 100
AT_FDCWD = -100
STATX_BASIC_STATS = 0x07FF
STATX_BTIME = 0x0800


class StatxTimestamp(ctypes.Structure):
    _fields_ = [
        ("seconds", ctypes.c_int64),
        ("nanoseconds", ctypes.c_uint32),
        ("reserved", ctypes.c_int32),
    ]


class StatxResult(ctypes.Structure):
    _fields_ = [
        ("mask", ctypes.c_uint32),
        ("block_size", ctypes.c_uint32),
        ("attributes", ctypes.c_uint64),
        ("link_count", ctypes.c_uint32),
        ("uid", ctypes.c_uint32),
        ("gid", ctypes.c_uint32),
        ("mode", ctypes.c_uint16),
        ("spare_zero", ctypes.c_uint16),
        ("inode", ctypes.c_uint64),
        ("size", ctypes.c_uint64),
        ("blocks", ctypes.c_uint64),
        ("attributes_mask", ctypes.c_uint64),
        ("access_time", StatxTimestamp),
        ("birth_time", StatxTimestamp),
        ("change_time", StatxTimestamp),
        ("modify_time", StatxTimestamp),
        ("rdev_major", ctypes.c_uint32),
        ("rdev_minor", ctypes.c_uint32),
        ("device_major", ctypes.c_uint32),
        ("device_minor", ctypes.c_uint32),
        ("mount_id", ctypes.c_uint64),
        ("dio_memory_alignment", ctypes.c_uint32),
        ("dio_offset_alignment", ctypes.c_uint32),
        ("spare", ctypes.c_uint64 * 12),
    ]


SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    objective TEXT NOT NULL,
    purpose TEXT NOT NULL,
    desired_state TEXT NOT NULL,
    success_criteria_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    repo_root TEXT NOT NULL,
    repo_device TEXT NOT NULL,
    repo_inode TEXT NOT NULL,
    repo_creation_kind TEXT NOT NULL,
    repo_creation_value TEXT NOT NULL,
    repo_path_key TEXT NOT NULL,
    repo_case_sensitive INTEGER NOT NULL CHECK (repo_case_sensitive IN (0, 1)),
    authority TEXT NOT NULL CHECK (authority IN ('read-only', 'local-write')),
    state TEXT NOT NULL CHECK (
        state IN (
            'active', 'waiting', 'blocked', 'verifying',
            'interrupted', 'complete', 'abandoned'
        )
    ),
    version INTEGER NOT NULL CHECK (version >= 1),
    lease_generation INTEGER NOT NULL CHECK (lease_generation >= 0),
    start_idempotency_key TEXT NOT NULL UNIQUE,
    start_payload_json TEXT NOT NULL,
    start_payload_hash TEXT NOT NULL,
    completion_summary TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('record', 'transition')),
    kind TEXT NOT NULL CHECK (
        kind IN (
            'checkpoint', 'progress', 'decision', 'evidence',
            'risk', 'blocker', 'opportunity', 'recovery'
        )
    ),
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    state_from TEXT,
    state_to TEXT,
    lease_generation INTEGER NOT NULL CHECK (lease_generation >= 1),
    created_at REAL NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE,
    UNIQUE (mission_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS leases (
    mission_id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK (generation >= 1),
    acquired_at REAL NOT NULL,
    heartbeat_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS missions_state_repo_idx
    ON missions(state, repo_root, updated_at);
CREATE INDEX IF NOT EXISTS missions_repo_identity_idx
    ON missions(
        repo_device, repo_inode, repo_creation_kind, repo_creation_value
    );
CREATE INDEX IF NOT EXISTS missions_repo_path_key_idx
    ON missions(repo_path_key);
CREATE INDEX IF NOT EXISTS events_mission_created_idx
    ON events(mission_id, id);
"""


class LedgerError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class DatabaseCaptureChanged(Exception):
    """The source database file-set changed while a snapshot was captured."""


@dataclass(frozen=True)
class DatabaseFileSnapshot:
    device: int
    inode: int
    size: int
    mtime_ns: int
    mode: int
    digest: str
    content: bytes

    def fingerprint(self) -> tuple[int, int, int, int, int, str]:
        return (
            self.device,
            self.inode,
            self.size,
            self.mtime_ns,
            self.mode,
            self.digest,
        )


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        write_error("invalid_arguments", message)
        raise SystemExit(2)


def default_db_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home) if codex_home else Path("~/.codex")
    return base / "outcome-owner" / "objectives.sqlite3"


def preflight_workspace_root() -> Path:
    if os.name == "posix":
        raw_root = Path("/tmp") / f".outcome-owner-preflight-{os.getuid()}"
    else:
        raw_root = Path("~/.codex/outcome-owner/preflight")
    try:
        return raw_root.expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise LedgerError(
            "unsafe_preflight_directory",
            "private preflight workspace could not be resolved",
        ) from exc


def canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def wire_json(payload: Any) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def require_text(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise LedgerError("invalid_input", f"{field} must be non-empty")
    return normalized


def normalize_repo_root(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError("invalid_repo_root", "repo-root must be non-empty")
    try:
        return Path(value).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise LedgerError(
            "invalid_repo_root",
            f"repo-root could not be resolved: {value}",
        ) from exc


def normalize_database_path(value: Path) -> Path:
    try:
        return value.expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise LedgerError(
            "invalid_db_path",
            f"database path could not be resolved: {value}",
        ) from exc


def validate_database_repo_separation(
    db_path: Path,
    repo_bindings: tuple[tuple[str, bool | None], ...],
) -> None:
    for stored_root, case_sensitive in repo_bindings:
        repo_root = Path(stored_root)
        db_parts = db_path.parts
        repo_parts = repo_root.parts
        if case_sensitive is False:
            db_parts = tuple(part.casefold() for part in db_parts)
            repo_parts = tuple(part.casefold() for part in repo_parts)
        if db_parts[: len(repo_parts)] == repo_parts:
            raise LedgerError(
                "invalid_db_path",
                "outcome ledger database must be outside every governed repository",
                details={"repo_root": stored_root},
            )


def validate_preflight_repo_separation(
    preflight_root: Path,
    repo_bindings: tuple[tuple[str, bool | None], ...],
) -> None:
    for stored_root, case_sensitive in repo_bindings:
        control_parts = preflight_root.parts
        repo_parts = Path(stored_root).parts
        if case_sensitive is False:
            control_parts = tuple(part.casefold() for part in control_parts)
            repo_parts = tuple(part.casefold() for part in repo_parts)
        if control_parts[: len(repo_parts)] == repo_parts:
            raise LedgerError(
                "invalid_repo_root",
                "governed repository must not contain the private preflight workspace",
                details={"repo_root": stored_root},
            )


def alternate_case_paths(path: Path) -> Iterator[Path]:
    parts = list(path.parts)
    for index in range(len(parts) - 1, 0, -1):
        component = parts[index]
        for character_index, character in enumerate(component):
            swapped = character.swapcase()
            if swapped != character and len(swapped) == 1:
                changed = component[:character_index] + swapped + component[character_index + 1 :]
                yield Path(*parts[:index], changed, *parts[index + 1 :])
                break


def alternate_component_exists_exactly(path: Path, candidate: Path) -> bool:
    for index, (original_part, candidate_part) in enumerate(
        zip(path.parts, candidate.parts, strict=True)
    ):
        if original_part == candidate_part:
            continue
        parent = Path(*path.parts[:index])
        try:
            with os.scandir(parent) as entries:
                return any(entry.name == candidate_part for entry in entries)
        except OSError as exc:
            raise LedgerError(
                "invalid_repo_root",
                f"repo-root case semantics could not be determined: {path}",
            ) from exc
    return False


def filesystem_is_case_sensitive(
    path: Path,
    path_stat: os.stat_result,
    *,
    stat_path: Callable[[Path], os.stat_result] = os.stat,
    exact_entry_exists: Callable[[Path, Path], bool] = alternate_component_exists_exactly,
) -> bool:
    for candidate in alternate_case_paths(path):
        if exact_entry_exists(path, candidate):
            return True
        try:
            candidate_stat = stat_path(candidate)
        except (FileNotFoundError, NotADirectoryError):
            return True
        except OSError as exc:
            raise LedgerError(
                "invalid_repo_root",
                f"repo-root case semantics could not be determined: {path}",
            ) from exc
        return (candidate_stat.st_dev, candidate_stat.st_ino) != (
            path_stat.st_dev,
            path_stat.st_ino,
        )
    return True


def filesystem_path_key(path: Path, case_sensitive: bool) -> str:
    rendered = str(path)
    return rendered if case_sensitive else rendered.casefold()


def verify_repo_identity_sample(path: Path, path_stat: os.stat_result) -> None:
    try:
        current_stat = path.stat()
    except OSError as exc:
        raise LedgerError(
            "invalid_repo_root",
            f"repo-root changed while its creation identity was inspected: {path}",
        ) from exc
    if (
        current_stat.st_dev != path_stat.st_dev
        or current_stat.st_ino != path_stat.st_ino
    ):
        raise LedgerError(
            "invalid_repo_root",
            f"repo-root changed while its creation identity was inspected: {path}",
        )


def linux_file_handle_creation_identity(
    path: Path,
    path_stat: os.stat_result,
) -> tuple[str, str] | None:
    if not sys.platform.startswith("linux"):
        return None
    try:
        function = ctypes.CDLL(None, use_errno=True).name_to_handle_at
    except (AttributeError, OSError):
        return None
    function.restype = ctypes.c_int
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
    ]
    unsupported_errors = {
        errno.EACCES,
        errno.EINVAL,
        errno.ENOSYS,
        errno.ENOTSUP,
        errno.EOPNOTSUPP,
        errno.EPERM,
    }
    capacity = 128
    for _attempt in range(2):
        class FileHandle(ctypes.Structure):
            _fields_ = [
                ("byte_count", ctypes.c_uint),
                ("handle_type", ctypes.c_int),
                ("value", ctypes.c_ubyte * capacity),
            ]

        handle = FileHandle()
        handle.byte_count = capacity
        mount_id = ctypes.c_int()
        ctypes.set_errno(0)
        result = function(
            AT_FDCWD,
            os.fsencode(path),
            ctypes.byref(handle),
            ctypes.byref(mount_id),
            0,
        )
        if result == 0:
            if handle.byte_count < 1 or handle.byte_count > capacity:
                return None
            verify_repo_identity_sample(path, path_stat)
            opaque_value = bytes(handle.value[: handle.byte_count]).hex()
            return "linux-file-handle", f"{handle.handle_type}:{opaque_value}"
        error_number = ctypes.get_errno()
        if error_number == errno.EOVERFLOW and capacity < handle.byte_count <= 4096:
            capacity = handle.byte_count
            continue
        if error_number in unsupported_errors:
            return None
        raise LedgerError(
            "invalid_repo_root",
            f"repo-root creation identity could not be inspected: {path}",
        ) from OSError(error_number, os.strerror(error_number), path)
    return None


def linux_birth_time_creation_identity(
    path: Path,
    path_stat: os.stat_result,
) -> tuple[str, str] | None:
    if not sys.platform.startswith("linux"):
        return None
    try:
        function = ctypes.CDLL(None, use_errno=True).statx
    except (AttributeError, OSError):
        return None
    function.restype = ctypes.c_int
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(StatxResult),
    ]
    result_buffer = StatxResult()
    ctypes.set_errno(0)
    result = function(
        AT_FDCWD,
        os.fsencode(path),
        0,
        STATX_BASIC_STATS | STATX_BTIME,
        ctypes.byref(result_buffer),
    )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number in {
            errno.EACCES,
            errno.EINVAL,
            errno.ENOSYS,
            errno.ENOTSUP,
            errno.EOPNOTSUPP,
            errno.EPERM,
        }:
            return None
        raise LedgerError(
            "invalid_repo_root",
            f"repo-root birth time could not be inspected: {path}",
        ) from OSError(error_number, os.strerror(error_number), path)
    if not result_buffer.mask & STATX_BTIME:
        return None
    sampled_device = os.makedev(
        result_buffer.device_major,
        result_buffer.device_minor,
    )
    if sampled_device != path_stat.st_dev or result_buffer.inode != path_stat.st_ino:
        raise LedgerError(
            "invalid_repo_root",
            f"repo-root changed while its birth time was inspected: {path}",
        )
    verify_repo_identity_sample(path, path_stat)
    birth_time = result_buffer.birth_time
    return (
        "linux-statx-birth-time",
        f"{birth_time.seconds}:{birth_time.nanoseconds:09d}",
    )


def try_repository_creation_identity_for_kind(
    path: Path,
    path_stat: os.stat_result,
    kind: str,
) -> tuple[str, str] | None:
    if kind == "linux-file-handle":
        return linux_file_handle_creation_identity(path, path_stat)
    if kind == "filesystem-generation":
        generation = getattr(path_stat, "st_gen", None)
        if isinstance(generation, int) and generation > 0:
            verify_repo_identity_sample(path, path_stat)
            return kind, str(generation)
        return None
    if kind == "linux-statx-birth-time":
        return linux_birth_time_creation_identity(path, path_stat)
    if kind == "filesystem-birth-time-ns":
        birth_time_ns = getattr(path_stat, "st_birthtime_ns", None)
        if isinstance(birth_time_ns, int):
            verify_repo_identity_sample(path, path_stat)
            return kind, str(birth_time_ns)
        birth_time = getattr(path_stat, "st_birthtime", None)
        if isinstance(birth_time, (int, float)) and math.isfinite(birth_time):
            verify_repo_identity_sample(path, path_stat)
            return kind, str(round(birth_time * 1_000_000_000))
        return None
    if kind == "windows-creation-time-ns" and os.name == "nt":
        creation_time_ns = getattr(path_stat, "st_ctime_ns", None)
        if isinstance(creation_time_ns, int):
            verify_repo_identity_sample(path, path_stat)
            return kind, str(creation_time_ns)
        return None
    return None


def repository_creation_identity_for_kind(
    path: Path,
    path_stat: os.stat_result,
    kind: str,
) -> tuple[str, str]:
    identity = try_repository_creation_identity_for_kind(path, path_stat, kind)
    if identity is not None:
        return identity
    raise LedgerError(
        "repo_identity_unavailable",
        "repo-root filesystem no longer exposes its recorded creation identity",
        details={"repo_root": str(path), "creation_kind": kind},
    )


def repository_creation_identity(
    path: Path,
    path_stat: os.stat_result,
) -> tuple[str, str]:
    for kind in REPO_CREATION_KIND_PRIORITY:
        identity = try_repository_creation_identity_for_kind(path, path_stat, kind)
        if identity is not None:
            return identity
    raise LedgerError(
        "repo_identity_unavailable",
        "repo-root filesystem does not expose a stable creation identity",
        details={"repo_root": str(path)},
    )


def repository_paths_overlap(
    first_root: str,
    first_case_sensitive: bool,
    second_root: str,
    second_case_sensitive: bool,
) -> bool:
    first_parts = Path(first_root).parts
    second_parts = Path(second_root).parts
    if not first_case_sensitive or not second_case_sensitive:
        first_parts = tuple(part.casefold() for part in first_parts)
        second_parts = tuple(part.casefold() for part in second_parts)
    common_length = min(len(first_parts), len(second_parts))
    return first_parts[:common_length] == second_parts[:common_length]


def repo_binding_error(row: sqlite3.Row, reason: str) -> LedgerError:
    return LedgerError(
        "repo_binding_mismatch",
        "mission repository binding no longer matches its immutable contract",
        details={
            "mission_id": row["id"],
            "repo_root": row["repo_root"],
            "reason": reason,
        },
    )


def validate_mission_repo_binding(row: sqlite3.Row) -> None:
    stored_root = row["repo_root"]
    try:
        current_root = Path(stored_root).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise repo_binding_error(row, "missing_or_unresolvable") from exc
    if str(current_root) != stored_root:
        raise repo_binding_error(row, "canonical_path_changed")
    try:
        current_stat = current_root.stat()
    except OSError as exc:
        raise repo_binding_error(row, "missing_or_unresolvable") from exc
    if not stat.S_ISDIR(current_stat.st_mode):
        raise repo_binding_error(row, "not_a_directory")
    if (
        str(current_stat.st_dev) != row["repo_device"]
        or str(current_stat.st_ino) != row["repo_inode"]
    ):
        raise repo_binding_error(row, "filesystem_identity_changed")
    try:
        creation_kind, creation_value = repository_creation_identity_for_kind(
            current_root,
            current_stat,
            row["repo_creation_kind"],
        )
    except LedgerError as exc:
        raise repo_binding_error(row, "creation_identity_unavailable") from exc
    if (
        creation_kind != row["repo_creation_kind"]
        or creation_value != row["repo_creation_value"]
    ):
        raise repo_binding_error(row, "filesystem_creation_identity_changed")
    try:
        case_sensitive = filesystem_is_case_sensitive(current_root, current_stat)
    except LedgerError as exc:
        raise repo_binding_error(row, "case_semantics_unavailable") from exc
    if case_sensitive != bool(row["repo_case_sensitive"]):
        raise repo_binding_error(row, "case_semantics_changed")
    if filesystem_path_key(current_root, case_sensitive) != row["repo_path_key"]:
        raise repo_binding_error(row, "filesystem_path_key_changed")


def iso_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def lease_expiry(now: float, ttl_seconds: float) -> float:
    expires_at = now + ttl_seconds
    if expires_at <= now:
        raise LedgerError(
            "invalid_input",
            "ttl-seconds is too small for the supported clock resolution",
        )
    try:
        iso_timestamp(expires_at)
    except (OverflowError, OSError, ValueError) as exc:
        raise LedgerError("invalid_input", "ttl-seconds is outside the supported range") from exc
    return expires_at


def logical_mutation_time(
    wall_time: float,
    mission: sqlite3.Row,
    lease: sqlite3.Row | None = None,
) -> float:
    candidates = [wall_time, float(mission["created_at"]), float(mission["updated_at"])]
    if lease is not None:
        candidates.extend(
            (float(lease["acquired_at"]), float(lease["heartbeat_at"]))
        )
    return max(candidates)


def write_json(payload: dict[str, Any], stream: Any = sys.stdout) -> None:
    stream.write(wire_json(payload) + "\n")


def write_error(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> None:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    write_json({"ok": False, "error": error}, sys.stderr)


def best_effort_chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def enforce_private_database_modes(db_path: Path) -> None:
    for suffix, path in database_state_paths(db_path):
        try:
            path_stat = os.lstat(path)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(path_stat.st_mode):
            raise LedgerError(
                "database_error",
                f"database state path is not a regular file: {path}",
            )
        if os.name != "posix":
            best_effort_chmod(path, 0o600)
            continue
        if stat.S_IMODE(path_stat.st_mode) != 0o600:
            try:
                os.chmod(path, 0o600, follow_symlinks=False)
            except OSError as exc:
                raise LedgerError(
                    "unsafe_database_permissions",
                    "outcome ledger file permissions could not be made private",
                    details={"file": suffix or "main"},
                ) from exc
        verified = os.lstat(path)
        if (
            not stat.S_ISREG(verified.st_mode)
            or stat.S_IMODE(verified.st_mode) != 0o600
        ):
            raise LedgerError(
                "unsafe_database_permissions",
                "outcome ledger file permissions are not private",
                details={"file": suffix or "main"},
            )


def ensure_private_preflight_workspace() -> Path:
    workspace = preflight_workspace_root()
    try:
        workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        workspace_stat = os.lstat(workspace)
    except OSError as exc:
        raise LedgerError(
            "unsafe_preflight_directory",
            "private preflight workspace could not be created or inspected",
        ) from exc
    if not stat.S_ISDIR(workspace_stat.st_mode) or stat.S_ISLNK(workspace_stat.st_mode):
        raise LedgerError(
            "unsafe_preflight_directory",
            "private preflight workspace is not a real directory",
        )
    if os.name == "posix":
        if (
            workspace_stat.st_uid != os.getuid()
            or stat.S_IMODE(workspace_stat.st_mode) != 0o700
        ):
            raise LedgerError(
                "unsafe_preflight_directory",
                "private preflight workspace must be owned by the current user with mode 0700",
            )
    return workspace


def database_sidecars(db_path: Path) -> tuple[Path, ...]:
    return tuple(
        Path(str(db_path) + suffix) for suffix in ("-journal", "-wal", "-shm")
    )


def existing_database_sidecars(db_path: Path) -> tuple[Path, ...]:
    return tuple(path for path in database_sidecars(db_path) if os.path.lexists(path))


def database_state_paths(db_path: Path) -> tuple[tuple[str, Path], ...]:
    return (
        ("", db_path),
        ("-journal", Path(str(db_path) + "-journal")),
        ("-wal", Path(str(db_path) + "-wal")),
        ("-shm", Path(str(db_path) + "-shm")),
    )


def capture_database_state(db_path: Path) -> dict[str, DatabaseFileSnapshot]:
    captured: dict[str, DatabaseFileSnapshot] = {}
    for suffix, path in database_state_paths(db_path):
        try:
            path_before = os.lstat(path)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(path_before.st_mode):
            raise LedgerError(
                "database_error",
                f"database state path is not a regular file: {path}",
            )

        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            file_descriptor = os.open(path, flags)
        except FileNotFoundError as exc:
            raise DatabaseCaptureChanged from exc
        try:
            descriptor_before = os.fstat(file_descriptor)
            if (
                descriptor_before.st_dev != path_before.st_dev
                or descriptor_before.st_ino != path_before.st_ino
            ):
                raise DatabaseCaptureChanged
            chunks: list[bytes] = []
            while True:
                chunk = os.read(file_descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            descriptor_after = os.fstat(file_descriptor)
        finally:
            os.close(file_descriptor)

        try:
            path_after = os.lstat(path)
        except FileNotFoundError as exc:
            raise DatabaseCaptureChanged from exc
        if not stat.S_ISREG(path_after.st_mode):
            raise DatabaseCaptureChanged
        stable_fields_before = (
            descriptor_before.st_dev,
            descriptor_before.st_ino,
            descriptor_before.st_size,
            descriptor_before.st_mtime_ns,
            stat.S_IMODE(descriptor_before.st_mode),
        )
        stable_fields_after = (
            descriptor_after.st_dev,
            descriptor_after.st_ino,
            descriptor_after.st_size,
            descriptor_after.st_mtime_ns,
            stat.S_IMODE(descriptor_after.st_mode),
        )
        stable_path_fields = (
            path_after.st_dev,
            path_after.st_ino,
            path_after.st_size,
            path_after.st_mtime_ns,
            stat.S_IMODE(path_after.st_mode),
        )
        if (
            stable_fields_before != stable_fields_after
            or stable_fields_after != stable_path_fields
        ):
            raise DatabaseCaptureChanged
        content = b"".join(chunks)
        captured[suffix] = DatabaseFileSnapshot(
            device=descriptor_after.st_dev,
            inode=descriptor_after.st_ino,
            size=descriptor_after.st_size,
            mtime_ns=descriptor_after.st_mtime_ns,
            mode=stat.S_IMODE(descriptor_after.st_mode),
            digest=hashlib.sha256(content).hexdigest(),
            content=content,
        )
    return captured


def database_state_fingerprints(
    captured: dict[str, DatabaseFileSnapshot],
) -> dict[str, tuple[int, int, int, int, int, str]]:
    return {suffix: snapshot.fingerprint() for suffix, snapshot in captured.items()}


def write_database_clone(
    captured: dict[str, DatabaseFileSnapshot],
    destination_directory: Path,
    database_name: str,
) -> Path:
    destination_directory.mkdir(mode=0o700)
    clone_path = destination_directory / database_name
    for suffix in ("", "-journal", "-wal"):
        snapshot = captured.get(suffix)
        if snapshot is None:
            continue
        destination = Path(str(clone_path) + suffix)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
        file_descriptor = os.open(destination, flags, 0o600)
        try:
            view = memoryview(snapshot.content)
            while view:
                written = os.write(file_descriptor, view)
                view = view[written:]
        finally:
            os.close(file_descriptor)
    return clone_path


def inspect_recovered_clone(
    clone_path: Path,
) -> tuple[
    int,
    int,
    set[tuple[str, str]],
    tuple[tuple[str, bool], ...],
]:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(clone_path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        repo_bindings: tuple[tuple[str, bool], ...] = ()
        if application_id == APPLICATION_ID and schema_version == SCHEMA_VERSION:
            repo_bindings = validate_identified_ledger(connection)
        objects = user_database_objects(connection)
        return application_id, schema_version, objects, repo_bindings
    except sqlite3.Error as exc:
        raise LedgerError(
            "database_error",
            f"database could not be safely inspected: {exc}",
        ) from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error:
                pass


def inspect_recovered_database(
    db_path: Path,
) -> tuple[
    int,
    int,
    set[tuple[str, str]],
    tuple[tuple[str, bool], ...],
    tuple[tuple[str, int], ...],
]:
    preflight_workspace = ensure_private_preflight_workspace()
    with tempfile.TemporaryDirectory(
        prefix=".outcome-owner-preflight-",
        dir=preflight_workspace,
    ) as temp_dir:
        temp_root = Path(temp_dir)
        for attempt in range(2):
            attempt_directory = temp_root / f"attempt-{attempt + 1}"
            try:
                before = capture_database_state(db_path)
                if "" not in before:
                    raise DatabaseCaptureChanged
                clone_path = write_database_clone(
                    before,
                    attempt_directory,
                    db_path.name,
                )
                inspection_error: LedgerError | None = None
                inspection: (
                    tuple[
                        int,
                        int,
                        set[tuple[str, str]],
                        tuple[tuple[str, bool], ...],
                    ]
                    | None
                ) = None
                try:
                    inspection = inspect_recovered_clone(clone_path)
                except LedgerError as exc:
                    inspection_error = exc
                after = capture_database_state(db_path)
            except DatabaseCaptureChanged:
                continue
            if database_state_fingerprints(before) != database_state_fingerprints(after):
                continue
            if inspection_error is not None:
                raise inspection_error
            if inspection is None:
                raise LedgerError(
                    "database_error",
                    "database snapshot inspection did not produce a result",
                )
            captured_modes = tuple(
                sorted((suffix, snapshot.mode) for suffix, snapshot in after.items())
            )
            return (*inspection, captured_modes)
    raise LedgerError(
        "database_busy",
        "database changed while a safe preflight snapshot was captured",
    )


def read_database_header_identity(db_path: Path) -> tuple[int, int] | None:
    with db_path.open("rb") as database_file:
        header = database_file.read(SQLITE_HEADER_SIZE)
    if not header:
        return None
    if len(header) < SQLITE_HEADER_SIZE or header[:16] != SQLITE_HEADER_MAGIC:
        raise LedgerError(
            "database_error",
            "database file does not have a valid SQLite header",
        )
    schema_version = struct.unpack(">I", header[60:64])[0]
    application_id = struct.unpack(">I", header[68:72])[0]
    return application_id, schema_version


def user_database_objects(connection: sqlite3.Connection) -> set[tuple[str, str]]:
    return {
        (row["type"], row["name"])
        for row in connection.execute(
            """
            SELECT type, name FROM sqlite_schema
            WHERE name NOT GLOB 'sqlite_*'
            """
        ).fetchall()
    }


def user_schema_signature(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, str, str, str | None], ...]:
    return tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_schema
            WHERE name NOT GLOB 'sqlite_*'
            ORDER BY type, name
            """
        ).fetchall()
    )


@lru_cache(maxsize=1)
def expected_schema_signature() -> tuple[tuple[str, str, str, str | None], ...]:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.executescript(SCHEMA)
        return user_schema_signature(connection)
    finally:
        connection.close()


def validate_expected_schema(connection: sqlite3.Connection) -> None:
    expected = expected_schema_signature()
    actual = user_schema_signature(connection)
    if actual == expected:
        return
    expected_by_name = {(item[0], item[1]): item for item in expected}
    actual_by_name = {(item[0], item[1]): item for item in actual}
    missing = sorted(
        f"{object_type}:{name}"
        for object_type, name in expected_by_name.keys() - actual_by_name.keys()
    )
    unexpected = sorted(
        f"{object_type}:{name}"
        for object_type, name in actual_by_name.keys() - expected_by_name.keys()
    )
    mismatched = sorted(
        f"{object_type}:{name}"
        for object_type, name in expected_by_name.keys() & actual_by_name.keys()
        if expected_by_name[(object_type, name)]
        != actual_by_name[(object_type, name)]
    )
    raise LedgerError(
        "invalid_ledger_schema",
        "identified outcome ledger does not match the supported schema",
        details={
            "missing": missing,
            "unexpected": unexpected,
            "mismatched": mismatched,
        },
    )


def persisted_data_error(table: str, row_id: Any, field: str) -> LedgerError:
    return LedgerError(
        "database_error",
        "persisted outcome ledger data is invalid",
        details={"table": table, "row_id": str(row_id), "field": field},
    )


def parse_persisted_json(
    value: Any,
    *,
    table: str,
    row_id: Any,
    field: str,
) -> Any:
    if not isinstance(value, str):
        raise persisted_data_error(table, row_id, field)
    try:
        parsed = json.loads(value)
        canonical = canonical_json(parsed)
    except (ValueError, TypeError, RecursionError) as exc:
        raise persisted_data_error(table, row_id, field) from exc
    if canonical != value:
        raise persisted_data_error(table, row_id, field)
    return parsed


def require_persisted_text(value: Any, table: str, row_id: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise persisted_data_error(table, row_id, field)
    return value


def require_persisted_time(value: Any, table: str, row_id: Any, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise persisted_data_error(table, row_id, field) from exc
    if not math.isfinite(parsed):
        raise persisted_data_error(table, row_id, field)
    try:
        iso_timestamp(parsed)
    except (OverflowError, OSError, ValueError) as exc:
        raise persisted_data_error(table, row_id, field) from exc
    return parsed


def require_persisted_string_list(
    value: Any,
    table: str,
    row_id: Any,
    field: str,
) -> list[str]:
    if not isinstance(value, list) or not value:
        raise persisted_data_error(table, row_id, field)
    for item in value:
        require_persisted_text(item, table, row_id, field)
    return value


def validate_mission_row(row: sqlite3.Row) -> None:
    row_id = row["id"]
    objective = require_persisted_text(row["objective"], "missions", row_id, "objective")
    purpose = require_persisted_text(row["purpose"], "missions", row_id, "purpose")
    desired_state = require_persisted_text(
        row["desired_state"], "missions", row_id, "desired_state"
    )
    criteria = require_persisted_string_list(
        parse_persisted_json(
            row["success_criteria_json"],
            table="missions",
            row_id=row_id,
            field="success_criteria_json",
        ),
        "missions",
        row_id,
        "success_criteria_json",
    )
    constraints = require_persisted_string_list(
        parse_persisted_json(
            row["constraints_json"],
            table="missions",
            row_id=row_id,
            field="constraints_json",
        ),
        "missions",
        row_id,
        "constraints_json",
    )
    repo_root = require_persisted_text(row["repo_root"], "missions", row_id, "repo_root")
    repo_device = require_persisted_text(
        row["repo_device"], "missions", row_id, "repo_device"
    )
    repo_inode = require_persisted_text(
        row["repo_inode"], "missions", row_id, "repo_inode"
    )
    repo_creation_kind = require_persisted_text(
        row["repo_creation_kind"],
        "missions",
        row_id,
        "repo_creation_kind",
    )
    repo_creation_value = require_persisted_text(
        row["repo_creation_value"],
        "missions",
        row_id,
        "repo_creation_value",
    )
    if repo_creation_kind not in REPO_CREATION_KINDS:
        raise persisted_data_error("missions", row_id, "repo_creation_kind")
    repo_path_key = require_persisted_text(
        row["repo_path_key"], "missions", row_id, "repo_path_key"
    )
    authority = require_persisted_text(
        row["authority"], "missions", row_id, "authority"
    )
    start_idempotency_key = require_persisted_text(
        row["start_idempotency_key"],
        "missions",
        row_id,
        "start_idempotency_key",
    )
    start_payload = parse_persisted_json(
        row["start_payload_json"],
        table="missions",
        row_id=row_id,
        field="start_payload_json",
    )
    expected_start_payload = {
        "authority": authority,
        "constraints": constraints,
        "desired_state": desired_state,
        "objective": objective,
        "purpose": purpose,
        "repo_identity": {
            "creation": {
                "kind": repo_creation_kind,
                "value": repo_creation_value,
            },
            "device": repo_device,
            "inode": repo_inode,
        },
        "repo_path": {
            "case_sensitive": bool(row["repo_case_sensitive"]),
            "key": repo_path_key,
        },
        "repo_root": repo_root,
        "success_criteria": criteria,
    }
    if start_payload != expected_start_payload:
        raise persisted_data_error("missions", row_id, "start_payload_json")
    if row["start_payload_hash"] != payload_hash(row["start_payload_json"]):
        raise persisted_data_error("missions", row_id, "start_payload_hash")
    created_at = require_persisted_time(
        row["created_at"], "missions", row_id, "created_at"
    )
    updated_at = require_persisted_time(
        row["updated_at"], "missions", row_id, "updated_at"
    )
    if updated_at < created_at:
        raise persisted_data_error("missions", row_id, "updated_at")
    completion_summary = row["completion_summary"]
    if row["state"] == "complete":
        require_persisted_text(
            completion_summary,
            "missions",
            row_id,
            "completion_summary",
        )
    elif completion_summary is not None:
        raise persisted_data_error("missions", row_id, "completion_summary")
    require_persisted_text(row_id, "missions", row_id, "id")
    if authority not in ("read-only", "local-write"):
        raise persisted_data_error("missions", row_id, "authority")
    if row["state"] not in MISSION_STATES:
        raise persisted_data_error("missions", row_id, "state")


def validate_event_row(row: sqlite3.Row) -> dict[str, Any]:
    row_id = row["id"]
    require_persisted_text(row["mission_id"], "events", row_id, "mission_id")
    summary = require_persisted_text(row["summary"], "events", row_id, "summary")
    require_persisted_text(
        row["idempotency_key"], "events", row_id, "idempotency_key"
    )
    require_persisted_time(row["created_at"], "events", row_id, "created_at")
    payload = parse_persisted_json(
        row["payload_json"],
        table="events",
        row_id=row_id,
        field="payload_json",
    )
    if not isinstance(payload, dict):
        raise persisted_data_error("events", row_id, "payload_json")
    if row["payload_hash"] != payload_hash(row["payload_json"]):
        raise persisted_data_error("events", row_id, "payload_hash")
    if payload.get("lease_generation") != row["lease_generation"]:
        raise persisted_data_error("events", row_id, "payload_json")
    if payload.get("summary") != summary:
        raise persisted_data_error("events", row_id, "payload_json")
    require_persisted_text(payload.get("owner"), "events", row_id, "payload_json")
    if row["action"] == "record":
        expected_keys = {"kind", "lease_generation", "metadata", "owner", "summary"}
        if set(payload) != expected_keys or not isinstance(payload.get("metadata"), dict):
            raise persisted_data_error("events", row_id, "payload_json")
        if payload.get("kind") != row["kind"] or row["kind"] not in EVENT_KINDS:
            raise persisted_data_error("events", row_id, "kind")
        if row["state_from"] is not None or row["state_to"] is not None:
            raise persisted_data_error("events", row_id, "state_from")
        return payload
    if row["action"] != "transition":
        raise persisted_data_error("events", row_id, "action")
    expected_keys = {
        "completion_summary",
        "expected_version",
        "lease_generation",
        "owner",
        "summary",
        "to_state",
    }
    if set(payload) != expected_keys or row["kind"] != "decision":
        raise persisted_data_error("events", row_id, "payload_json")
    state_from = row["state_from"]
    state_to = row["state_to"]
    if (
        state_from not in ALLOWED_TRANSITIONS
        or state_to not in ALLOWED_TRANSITIONS[state_from]
        or payload.get("to_state") != state_to
    ):
        raise persisted_data_error("events", row_id, "state_to")
    expected_version = payload.get("expected_version")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int):
        raise persisted_data_error("events", row_id, "payload_json")
    if expected_version < 1:
        raise persisted_data_error("events", row_id, "payload_json")
    completion_summary = payload.get("completion_summary")
    if state_to == "complete":
        require_persisted_text(
            completion_summary,
            "events",
            row_id,
            "payload_json",
        )
    elif completion_summary is not None:
        raise persisted_data_error("events", row_id, "payload_json")
    return payload


def validate_persisted_rows(connection: sqlite3.Connection) -> None:
    foreign_key_failures = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_failures:
        raise LedgerError(
            "database_error",
            "persisted outcome ledger data violates foreign keys",
        )
    missions = connection.execute("SELECT * FROM missions").fetchall()
    missions_by_id = {row["id"]: row for row in missions}
    for mission in missions:
        validate_mission_row(mission)
    last_event_times = {
        mission_id: float(mission["created_at"])
        for mission_id, mission in missions_by_id.items()
    }
    replay_states = {mission_id: "active" for mission_id in missions_by_id}
    replay_versions = {mission_id: 1 for mission_id in missions_by_id}
    replay_completion_summaries: dict[str, str | None] = {
        mission_id: None for mission_id in missions_by_id
    }
    latest_verifying_events: dict[str, int | None] = {
        mission_id: None for mission_id in missions_by_id
    }
    evidence_generations_since_verifying: dict[str, set[int]] = {
        mission_id: set() for mission_id in missions_by_id
    }
    last_event_generations = {mission_id: 0 for mission_id in missions_by_id}
    state_entry_generations = {mission_id: 0 for mission_id in missions_by_id}
    events = connection.execute("SELECT * FROM events ORDER BY id").fetchall()
    for event in events:
        payload = validate_event_row(event)
        mission = missions_by_id.get(event["mission_id"])
        if mission is None or event["lease_generation"] > mission["lease_generation"]:
            raise persisted_data_error("events", event["id"], "lease_generation")
        mission_id = event["mission_id"]
        if event["lease_generation"] < last_event_generations[mission_id]:
            raise persisted_data_error("events", event["id"], "lease_generation")
        last_event_generations[mission_id] = event["lease_generation"]
        event_time = float(event["created_at"])
        if (
            event_time < last_event_times[mission_id]
            or event_time > float(mission["updated_at"])
        ):
            raise persisted_data_error("events", event["id"], "created_at")
        last_event_times[mission_id] = event_time
        if replay_states[mission_id] in TERMINAL_STATES:
            raise persisted_data_error("events", event["id"], "action")
        if event["action"] == "record":
            if (
                event["kind"] == "evidence"
                and latest_verifying_events[mission_id] is not None
            ):
                evidence_generations_since_verifying[mission_id].add(
                    event["lease_generation"]
                )
            continue
        if event["action"] == "transition":
            if event["state_from"] != replay_states[mission_id]:
                raise persisted_data_error("events", event["id"], "state_from")
            if payload["expected_version"] != replay_versions[mission_id]:
                raise persisted_data_error("events", event["id"], "payload_json")
            if (
                event["state_to"] == "complete"
                and event["lease_generation"]
                not in evidence_generations_since_verifying[mission_id]
            ):
                raise persisted_data_error(
                    "events",
                    event["id"],
                    "completion_evidence",
                )
            replay_states[mission_id] = event["state_to"]
            replay_versions[mission_id] += 1
            replay_completion_summaries[mission_id] = payload["completion_summary"]
            state_entry_generations[mission_id] = event["lease_generation"]
            if event["state_to"] == "verifying":
                latest_verifying_events[mission_id] = event["id"]
                evidence_generations_since_verifying[mission_id].clear()
    for mission_id, mission in missions_by_id.items():
        if mission["version"] != replay_versions[mission_id]:
            raise persisted_data_error("missions", mission_id, "version")
        if mission["state"] != replay_states[mission_id]:
            raise persisted_data_error("missions", mission_id, "state")
        if (
            mission["state"] == "complete"
            and mission["completion_summary"]
            != replay_completion_summaries[mission_id]
        ):
            raise persisted_data_error(
                "missions",
                mission_id,
                "completion_summary",
            )
    for lease in connection.execute("SELECT * FROM leases").fetchall():
        mission = missions_by_id.get(lease["mission_id"])
        if mission is None or lease["generation"] != mission["lease_generation"]:
            raise persisted_data_error("leases", lease["mission_id"], "generation")
        if mission["state"] in TERMINAL_STATES:
            raise persisted_data_error("leases", lease["mission_id"], "mission_id")
        if (
            mission["state"] in LEASE_RELEASING_STATES
            and lease["generation"] <= state_entry_generations[lease["mission_id"]]
        ):
            raise persisted_data_error("leases", lease["mission_id"], "generation")
        require_persisted_text(
            lease["owner"], "leases", lease["mission_id"], "owner"
        )
        acquired_at = require_persisted_time(
            lease["acquired_at"], "leases", lease["mission_id"], "acquired_at"
        )
        heartbeat_at = require_persisted_time(
            lease["heartbeat_at"], "leases", lease["mission_id"], "heartbeat_at"
        )
        expires_at = require_persisted_time(
            lease["expires_at"], "leases", lease["mission_id"], "expires_at"
        )
        if acquired_at > heartbeat_at or heartbeat_at >= expires_at:
            raise persisted_data_error("leases", lease["mission_id"], "expires_at")
        if heartbeat_at > float(mission["updated_at"]):
            raise persisted_data_error("leases", lease["mission_id"], "heartbeat_at")


def validate_identified_ledger(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, bool], ...]:
    with read_transaction(connection):
        validate_expected_schema(connection)
        quick_check = connection.execute("PRAGMA quick_check").fetchall()
        if [row[0] for row in quick_check] != ["ok"]:
            raise LedgerError(
                "database_error",
                "outcome ledger failed SQLite integrity validation",
            )
        validate_persisted_rows(connection)
        return tuple(
            (row[0], bool(row[1]))
            for row in connection.execute(
                """
                SELECT DISTINCT repo_root, repo_case_sensitive
                FROM missions
                ORDER BY repo_root, repo_case_sensitive
                """
            ).fetchall()
        )


def preflight_database(db_path: Path) -> bool:
    sidecars = existing_database_sidecars(db_path)
    if not os.path.lexists(db_path):
        if sidecars:
            raise LedgerError(
                "database_identity_mismatch",
                "database sidecars exist without an identified outcome ledger",
            )
        return True

    application_id, schema_version, user_objects, repo_bindings, captured_modes = (
        inspect_recovered_database(db_path)
    )
    captured_mode_map = dict(captured_modes)
    captured_sidecars = set(captured_mode_map) - {""}
    if application_id not in (0, APPLICATION_ID):
        raise LedgerError(
            "database_identity_mismatch",
            "database belongs to a different application",
            details={"application_id": application_id},
        )
    if application_id == APPLICATION_ID:
        if schema_version != SCHEMA_VERSION:
            raise LedgerError(
                "unsupported_schema_version",
                f"unsupported outcome ledger schema version: {schema_version}",
                details={
                    "current_version": schema_version,
                    "supported_version": SCHEMA_VERSION,
                },
            )
        user_tables = {
            name for object_type, name in user_objects if object_type == "table"
        }
        if not REQUIRED_TABLES.issubset(user_tables):
            raise LedgerError(
                "invalid_ledger_schema",
                "identified outcome ledger is missing required tables",
                details={"required_tables": sorted(REQUIRED_TABLES)},
            )
        if os.name == "posix":
            unsafe_modes = {
                suffix or "main": f"{mode:04o}"
                for suffix, mode in captured_modes
                if mode != 0o600
            }
            if unsafe_modes:
                raise LedgerError(
                    "unsafe_database_permissions",
                    "identified outcome ledger files must use mode 0600",
                    details={"files": unsafe_modes},
                )
        validate_database_repo_separation(db_path, repo_bindings)
        validate_preflight_repo_separation(
            preflight_workspace_root(),
            repo_bindings,
        )
        return False
    if schema_version != 0 or captured_sidecars:
        raise LedgerError(
            "database_identity_mismatch",
            "database is not an empty unidentified outcome ledger",
            details={
                "application_id": application_id,
                "schema_version": schema_version,
            },
        )
    if user_objects:
        raise LedgerError(
            "database_identity_mismatch",
            "database is not an empty unidentified outcome ledger",
            details={
                "application_id": application_id,
                "schema_version": schema_version,
            },
        )
    return True


def connect_database(db_path: Path) -> sqlite3.Connection:
    db_path = normalize_database_path(db_path)
    parent_existed = db_path.parent.exists()
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    initialize = preflight_database(db_path)

    connection = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    try:
        connection.row_factory = sqlite3.Row
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        user_objects = user_database_objects(connection)

        if initialize and (application_id != 0 or schema_version != 0 or user_objects):
            raise LedgerError(
                "database_identity_mismatch",
                "database changed after preflight and is no longer empty",
                details={
                    "application_id": application_id,
                    "schema_version": schema_version,
                },
            )
        if not initialize and application_id != APPLICATION_ID:
            raise LedgerError(
                "database_identity_mismatch",
                "database identity changed after preflight",
                details={"application_id": application_id},
            )
        if not initialize and schema_version != SCHEMA_VERSION:
            raise LedgerError(
                "unsupported_schema_version",
                f"unsupported outcome ledger schema version: {schema_version}",
                details={"current_version": schema_version, "supported_version": SCHEMA_VERSION},
            )
        if not initialize:
            validate_identified_ledger(connection)

        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA synchronous = FULL")
        if initialize:
            journal_mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
            if journal_mode.lower() != "delete":
                raise LedgerError(
                    "database_error",
                    "could not initialize the outcome ledger in rollback-journal mode",
                )
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + SCHEMA
                + f"\nPRAGMA application_id = {APPLICATION_ID};"
                + f"\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;"
            )
            if read_database_header_identity(db_path) != (
                APPLICATION_ID,
                SCHEMA_VERSION,
            ):
                raise LedgerError(
                    "database_error",
                    "outcome ledger identity was not durable in the main database header",
                )
            validate_identified_ledger(connection)
        current_journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if current_journal.lower() != "wal":
            try:
                connection.execute("PRAGMA journal_mode = WAL").fetchone()
            except sqlite3.OperationalError:
                # Some filesystems do not support WAL. SQLite still provides transactions.
                pass
        try:
            default_path = normalize_database_path(default_db_path())
        except LedgerError:
            default_path = None
        if not parent_existed or db_path == default_path:
            best_effort_chmod(db_path.parent, 0o700)
        enforce_private_database_modes(db_path)
        return connection
    except BaseException:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass
        try:
            connection.close()
        except sqlite3.Error:
            pass
        raise


@contextmanager
def immediate_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


@contextmanager
def read_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def mission_from_row(row: sqlite3.Row) -> dict[str, Any]:
    success_criteria = parse_persisted_json(
        row["success_criteria_json"],
        table="missions",
        row_id=row["id"],
        field="success_criteria_json",
    )
    constraints = parse_persisted_json(
        row["constraints_json"],
        table="missions",
        row_id=row["id"],
        field="constraints_json",
    )
    return {
        "id": row["id"],
        "objective": row["objective"],
        "purpose": row["purpose"],
        "desired_state": row["desired_state"],
        "success_criteria": success_criteria,
        "constraints": constraints,
        "repo_root": row["repo_root"],
        "repo_identity": {
            "creation": {
                "kind": row["repo_creation_kind"],
                "value": row["repo_creation_value"],
            },
            "device": row["repo_device"],
            "inode": row["repo_inode"],
        },
        "repo_path_case_sensitive": bool(row["repo_case_sensitive"]),
        "authority": row["authority"],
        "state": row["state"],
        "version": row["version"],
        "lease_generation": row["lease_generation"],
        "completion_summary": row["completion_summary"],
        "created_at": iso_timestamp(row["created_at"]),
        "updated_at": iso_timestamp(row["updated_at"]),
    }


def event_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = parse_persisted_json(
        row["payload_json"],
        table="events",
        row_id=row["id"],
        field="payload_json",
    )
    event = {
        "id": row["id"],
        "mission_id": row["mission_id"],
        "action": row["action"],
        "kind": row["kind"],
        "summary": row["summary"],
        "idempotency_key": row["idempotency_key"],
        "lease_generation": row["lease_generation"],
        "payload": payload,
        "created_at": iso_timestamp(row["created_at"]),
    }
    if row["state_from"] is not None:
        event["state_from"] = row["state_from"]
    if row["state_to"] is not None:
        event["state_to"] = row["state_to"]
    return event


def lease_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "mission_id": row["mission_id"],
        "owner": row["owner"],
        "generation": row["generation"],
        "acquired_at": iso_timestamp(row["acquired_at"]),
        "heartbeat_at": iso_timestamp(row["heartbeat_at"]),
        "expires_at": iso_timestamp(row["expires_at"]),
    }


def require_mission(connection: sqlite3.Connection, mission_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM missions WHERE id = ?",
        (mission_id,),
    ).fetchone()
    if row is None:
        raise LedgerError("mission_not_found", f"mission not found: {mission_id}")
    return row


def reject_terminal(row: sqlite3.Row) -> None:
    if row["state"] in TERMINAL_STATES:
        raise LedgerError(
            "terminal_state",
            f"mission {row['id']} is terminal in state {row['state']}",
        )


def require_current_lease(
    connection: sqlite3.Connection,
    mission_id: str,
    owner: str,
    lease_generation: int,
    now: float,
) -> sqlite3.Row:
    lease = connection.execute(
        "SELECT * FROM leases WHERE mission_id = ?",
        (mission_id,),
    ).fetchone()
    if lease is None:
        raise LedgerError(
            "lease_required",
            f"mission {mission_id} has no active owner lease",
        )
    if lease["generation"] != lease_generation:
        raise LedgerError(
            "lease_generation_conflict",
            "lease generation does not match the current owner lease",
            details={"current_generation": lease["generation"]},
        )
    if lease["expires_at"] <= now:
        raise LedgerError(
            "lease_expired",
            f"owner lease for mission {mission_id} has expired",
            details={"expired_at": iso_timestamp(lease["expires_at"])},
        )
    if lease["owner"] != owner:
        raise LedgerError(
            "lease_not_owned",
            f"mission {mission_id} is owned by a different active owner",
            details={"expires_at": iso_timestamp(lease["expires_at"])},
        )
    return lease


def find_idempotent_event(
    connection: sqlite3.Connection,
    mission_id: str,
    idempotency_key: str,
    expected_action: str,
    expected_payload_json: str,
) -> sqlite3.Row | None:
    row = connection.execute(
        "SELECT * FROM events WHERE mission_id = ? AND idempotency_key = ?",
        (mission_id, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    if row["action"] != expected_action or row["payload_json"] != expected_payload_json:
        raise LedgerError(
            "idempotency_conflict",
            "idempotency key was already used with a different canonical payload",
            details={"idempotency_key": idempotency_key},
        )
    return row


def command_start(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    objective = require_text(args.objective, "objective")
    purpose = require_text(args.purpose, "purpose")
    desired_state = require_text(args.desired_state, "desired-state")
    criteria = [require_text(item, "success-criterion") for item in args.success_criterion]
    if not criteria:
        raise LedgerError(
            "invalid_input",
            "at least one success-criterion is required",
        )
    constraints = [require_text(item, "constraint") for item in args.constraint]
    if not constraints:
        raise LedgerError("invalid_input", "at least one constraint is required")
    idempotency_key = require_text(args.idempotency_key, "idempotency-key")
    repo_root = normalize_repo_root(args.repo_root)
    payload_without_identity = {
        "authority": args.authority,
        "constraints": constraints,
        "desired_state": desired_state,
        "objective": objective,
        "purpose": purpose,
        "repo_root": str(repo_root),
        "success_criteria": criteria,
    }

    with immediate_transaction(connection):
        existing = connection.execute(
            "SELECT * FROM missions WHERE start_idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            replay_payload = {
                **payload_without_identity,
                "repo_identity": {
                    "creation": {
                        "kind": existing["repo_creation_kind"],
                        "value": existing["repo_creation_value"],
                    },
                    "device": existing["repo_device"],
                    "inode": existing["repo_inode"],
                },
                "repo_path": {
                    "case_sensitive": bool(existing["repo_case_sensitive"]),
                    "key": existing["repo_path_key"],
                },
            }
            canonical_payload = canonical_json(replay_payload)
            if existing["start_payload_json"] != canonical_payload:
                raise LedgerError(
                    "idempotency_conflict",
                    "start idempotency key was already used with a different canonical payload",
                    details={"idempotency_key": idempotency_key},
                )
            return {"ok": True, "replayed": True, "mission": mission_from_row(existing)}

        try:
            repo_stat = repo_root.stat()
        except OSError as exc:
            raise LedgerError(
                "invalid_repo_root",
                f"repo-root must resolve to an existing directory: {repo_root}",
            ) from exc
        if not stat.S_ISDIR(repo_stat.st_mode):
            raise LedgerError(
                "invalid_repo_root",
                f"repo-root must resolve to an existing directory: {repo_root}",
            )
        repo_device = str(repo_stat.st_dev)
        repo_inode = str(repo_stat.st_ino)
        repo_creation_kind, repo_creation_value = repository_creation_identity(
            repo_root,
            repo_stat,
        )
        repo_case_sensitive = filesystem_is_case_sensitive(
            repo_root,
            repo_stat,
        )
        repo_path_key = filesystem_path_key(repo_root, repo_case_sensitive)
        payload = {
            **payload_without_identity,
            "repo_identity": {
                "creation": {
                    "kind": repo_creation_kind,
                    "value": repo_creation_value,
                },
                "device": repo_device,
                "inode": repo_inode,
            },
            "repo_path": {
                "case_sensitive": repo_case_sensitive,
                "key": repo_path_key,
            },
        }
        canonical_payload = canonical_json(payload)
        now = time.time()
        mission_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO missions (
                id, objective, purpose, desired_state, success_criteria_json,
                constraints_json, repo_root, repo_device, repo_inode,
                repo_creation_kind, repo_creation_value, repo_path_key,
                repo_case_sensitive, authority, state, version,
                lease_generation, start_idempotency_key, start_payload_json,
                start_payload_hash, completion_summary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, 0, ?, ?, ?, NULL, ?, ?)
            """,
            (
                mission_id,
                objective,
                purpose,
                desired_state,
                canonical_json(criteria),
                canonical_json(constraints),
                str(repo_root),
                repo_device,
                repo_inode,
                repo_creation_kind,
                repo_creation_value,
                repo_path_key,
                int(repo_case_sensitive),
                args.authority,
                idempotency_key,
                canonical_payload,
                payload_hash(canonical_payload),
                now,
                now,
            ),
        )
        row = require_mission(connection, mission_id)
        return {"ok": True, "replayed": False, "mission": mission_from_row(row)}


def command_list(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    where: list[str] = []
    values: list[Any] = []
    filters: dict[str, Any] = {"state": args.state, "repo_root": None}
    if args.state:
        where.append("state = ?")
        values.append(args.state)
    if args.repo_root is not None:
        repo_path = normalize_repo_root(args.repo_root)
        repo_root = str(repo_path)
        repo_path_key = repo_root.casefold()
        try:
            repo_stat = repo_path.stat()
        except OSError:
            repo_stat = None
        if repo_stat is not None and stat.S_ISDIR(repo_stat.st_mode):
            repo_creation_kind, repo_creation_value = repository_creation_identity(
                repo_path,
                repo_stat,
            )
            where.append(
                """
                (repo_root = ?
                 OR (repo_case_sensitive = 0 AND repo_path_key = ?)
                 OR (repo_device = ? AND repo_inode = ?
                     AND repo_creation_kind = ? AND repo_creation_value = ?))
                """
            )
            values.extend(
                (
                    repo_root,
                    repo_path_key,
                    str(repo_stat.st_dev),
                    str(repo_stat.st_ino),
                    repo_creation_kind,
                    repo_creation_value,
                )
            )
        else:
            where.append(
                "(repo_root = ? OR (repo_case_sensitive = 0 AND repo_path_key = ?))"
            )
            values.extend((repo_root, repo_path_key))
        filters["repo_root"] = repo_root
    base_query = " FROM missions"
    if where:
        base_query += " WHERE " + " AND ".join(where)
    with read_transaction(connection):
        total = connection.execute("SELECT COUNT(*)" + base_query, values).fetchone()[0]
        query = "SELECT *" + base_query
        query += " ORDER BY updated_at DESC, id ASC LIMIT ?"
        values.append(args.limit)
        rows = connection.execute(query, values).fetchall()
    return {
        "ok": True,
        "count": len(rows),
        "total_count": total,
        "truncated": len(rows) < total,
        "filters": filters,
        "missions": [mission_from_row(row) for row in rows],
    }


def command_show(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    with read_transaction(connection):
        now = time.time()
        mission = require_mission(connection, args.mission_id)
        lease = connection.execute(
            "SELECT * FROM leases WHERE mission_id = ? AND expires_at > ?",
            (args.mission_id, now),
        ).fetchone()
        total_events = connection.execute(
            "SELECT COUNT(*) FROM events WHERE mission_id = ?",
            (args.mission_id,),
        ).fetchone()[0]
        recent_desc = connection.execute(
            """
            SELECT * FROM events
            WHERE mission_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (args.mission_id, args.events_limit),
        ).fetchall()
    events = [event_from_row(row) for row in reversed(recent_desc)]
    return {
        "ok": True,
        "mission": mission_from_row(mission),
        "active_lease": lease_from_row(lease) if lease is not None else None,
        "events": events,
        "events_returned": len(events),
        "events_total": total_events,
    }


def command_claim(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    owner = require_text(args.owner, "owner")
    with immediate_transaction(connection):
        wall_time = time.time()
        mission = require_mission(connection, args.mission_id)
        if mission["version"] != args.expected_version:
            raise LedgerError(
                "version_conflict",
                "mission version changed before claim",
                details={"current_version": mission["version"]},
            )
        reject_terminal(mission)
        if mission["lease_generation"] != args.expected_generation:
            raise LedgerError(
                "lease_generation_conflict",
                "mission lease generation changed before claim",
                details={"current_generation": mission["lease_generation"]},
            )
        validate_mission_repo_binding(mission)
        existing = connection.execute(
            "SELECT * FROM leases WHERE mission_id = ?",
            (args.mission_id,),
        ).fetchone()
        active = existing is not None and existing["expires_at"] > wall_time
        if active and existing["owner"] != owner:
            raise LedgerError(
                "lease_conflict",
                f"mission {args.mission_id} already has an active owner lease",
                details={"expires_at": iso_timestamp(existing["expires_at"])},
            )
        renewed = bool(active and existing["owner"] == owner)
        active_missions = connection.execute(
            """
            SELECT missions.*, leases.expires_at AS active_lease_expires_at
            FROM leases
            JOIN missions ON missions.id = leases.mission_id
            WHERE leases.mission_id != ?
              AND leases.expires_at > ?
              AND (? = 'local-write' OR missions.authority = 'local-write')
            ORDER BY leases.expires_at ASC
            """,
            (
                args.mission_id,
                wall_time,
                mission["authority"],
            ),
        ).fetchall()
        for active_mission in active_missions:
            validate_mission_repo_binding(active_mission)
        repo_conflicts = [
            active_mission
            for active_mission in active_missions
            if (
                (
                    active_mission["repo_device"] == mission["repo_device"]
                    and active_mission["repo_inode"] == mission["repo_inode"]
                    and active_mission["repo_creation_kind"]
                    == mission["repo_creation_kind"]
                    and active_mission["repo_creation_value"]
                    == mission["repo_creation_value"]
                )
                or active_mission["repo_root"] == mission["repo_root"]
                or active_mission["repo_path_key"] == mission["repo_path_key"]
                or repository_paths_overlap(
                    active_mission["repo_root"],
                    bool(active_mission["repo_case_sensitive"]),
                    mission["repo_root"],
                    bool(mission["repo_case_sensitive"]),
                )
            )
        ]
        if repo_conflicts:
            raise LedgerError(
                "repo_lease_conflict",
                "repository has an incompatible active mission lease",
                details={
                    "repo_root": mission["repo_root"],
                    "expires_at": iso_timestamp(
                        repo_conflicts[0]["active_lease_expires_at"]
                    ),
                },
            )
        now = logical_mutation_time(wall_time, mission, existing)
        expires_at = lease_expiry(now, args.ttl_seconds)
        generation = existing["generation"] if renewed else mission["lease_generation"] + 1
        if renewed:
            connection.execute(
                "UPDATE missions SET updated_at = ? WHERE id = ?",
                (now, args.mission_id),
            )
        else:
            connection.execute(
                """
                UPDATE missions
                SET lease_generation = ?, updated_at = ?
                WHERE id = ?
                """,
                (generation, now, args.mission_id),
            )
        acquired_at = existing["acquired_at"] if renewed else now
        connection.execute(
            """
            INSERT INTO leases (
                mission_id, owner, generation, acquired_at, heartbeat_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(mission_id) DO UPDATE SET
                owner = excluded.owner,
                generation = excluded.generation,
                acquired_at = excluded.acquired_at,
                heartbeat_at = excluded.heartbeat_at,
                expires_at = excluded.expires_at
            """,
            (args.mission_id, owner, generation, acquired_at, now, expires_at),
        )
        lease = connection.execute(
            "SELECT * FROM leases WHERE mission_id = ?",
            (args.mission_id,),
        ).fetchone()
        current_mission = require_mission(connection, args.mission_id)
        return {
            "ok": True,
            "renewed": renewed,
            "mission": mission_from_row(current_mission),
            "lease": lease_from_row(lease),
        }


def command_heartbeat(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    owner = require_text(args.owner, "owner")
    with immediate_transaction(connection):
        wall_time = time.time()
        mission = require_mission(connection, args.mission_id)
        reject_terminal(mission)
        lease = require_current_lease(
            connection,
            args.mission_id,
            owner,
            args.lease_generation,
            wall_time,
        )
        validate_mission_repo_binding(mission)
        now = logical_mutation_time(wall_time, mission, lease)
        expires_at = lease_expiry(now, args.ttl_seconds)
        connection.execute(
            """
            UPDATE leases
            SET heartbeat_at = ?, expires_at = ?
            WHERE mission_id = ?
            """,
            (now, expires_at, args.mission_id),
        )
        connection.execute(
            "UPDATE missions SET updated_at = ? WHERE id = ?",
            (now, args.mission_id),
        )
        lease = connection.execute(
            "SELECT * FROM leases WHERE mission_id = ?",
            (args.mission_id,),
        ).fetchone()
        return {"ok": True, "lease": lease_from_row(lease)}


def command_record(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    owner = require_text(args.owner, "owner")
    summary = require_text(args.summary, "summary")
    idempotency_key = require_text(args.idempotency_key, "idempotency-key")
    try:
        metadata = json.loads(args.metadata_json)
    except (ValueError, RecursionError) as exc:
        raise LedgerError("invalid_metadata_json", f"metadata-json is not valid JSON: {exc}") from exc
    if not isinstance(metadata, dict):
        raise LedgerError("invalid_metadata_json", "metadata-json must be a JSON object")
    payload = {
        "kind": args.kind,
        "lease_generation": args.lease_generation,
        "metadata": metadata,
        "owner": owner,
        "summary": summary,
    }
    try:
        canonical_payload = canonical_json(payload)
    except (ValueError, RecursionError) as exc:
        raise LedgerError(
            "invalid_metadata_json",
            "metadata-json must contain finite JSON values",
        ) from exc
    with immediate_transaction(connection):
        mission = require_mission(connection, args.mission_id)
        existing = find_idempotent_event(
            connection,
            args.mission_id,
            idempotency_key,
            "record",
            canonical_payload,
        )
        if existing is not None:
            return {"ok": True, "replayed": True, "event": event_from_row(existing)}
        wall_time = time.time()
        reject_terminal(mission)
        lease = require_current_lease(
            connection,
            args.mission_id,
            owner,
            args.lease_generation,
            wall_time,
        )
        validate_mission_repo_binding(mission)
        now = logical_mutation_time(wall_time, mission, lease)
        cursor = connection.execute(
            """
            INSERT INTO events (
                mission_id, action, kind, summary, payload_json, payload_hash,
                idempotency_key, state_from, state_to, lease_generation, created_at
            ) VALUES (?, 'record', ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                args.mission_id,
                args.kind,
                summary,
                canonical_payload,
                payload_hash(canonical_payload),
                idempotency_key,
                lease["generation"],
                now,
            ),
        )
        connection.execute(
            "UPDATE missions SET updated_at = ? WHERE id = ?",
            (now, args.mission_id),
        )
        event = connection.execute(
            "SELECT * FROM events WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return {"ok": True, "replayed": False, "event": event_from_row(event)}


def command_transition(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    owner = require_text(args.owner, "owner")
    summary = require_text(args.summary, "summary")
    idempotency_key = require_text(args.idempotency_key, "idempotency-key")
    completion_summary = None
    if args.to_state == "complete":
        completion_summary = require_text(args.completion_summary or "", "completion-summary")
    elif args.completion_summary and args.completion_summary.strip():
        raise LedgerError(
            "invalid_input",
            "completion-summary is only valid when transitioning to complete",
        )
    payload = {
        "completion_summary": completion_summary,
        "expected_version": args.expected_version,
        "lease_generation": args.lease_generation,
        "owner": owner,
        "summary": summary,
        "to_state": args.to_state,
    }
    canonical_payload = canonical_json(payload)
    with immediate_transaction(connection):
        mission = require_mission(connection, args.mission_id)
        existing = find_idempotent_event(
            connection,
            args.mission_id,
            idempotency_key,
            "transition",
            canonical_payload,
        )
        if existing is not None:
            current = require_mission(connection, args.mission_id)
            active_lease = connection.execute(
                "SELECT * FROM leases WHERE mission_id = ? AND expires_at > ?",
                (args.mission_id, time.time()),
            ).fetchone()
            return {
                "ok": True,
                "replayed": True,
                "event_effect": {
                    "lease_released": existing["state_to"] in LEASE_RELEASING_STATES
                },
                "event": event_from_row(existing),
                "mission": mission_from_row(current),
                "active_lease": (
                    lease_from_row(active_lease) if active_lease is not None else None
                ),
            }

        if mission["version"] != args.expected_version:
            raise LedgerError(
                "version_conflict",
                "mission version changed before transition",
                details={"current_version": mission["version"]},
            )
        reject_terminal(mission)
        wall_time = time.time()
        lease = require_current_lease(
            connection,
            args.mission_id,
            owner,
            args.lease_generation,
            wall_time,
        )
        validate_mission_repo_binding(mission)
        now = logical_mutation_time(wall_time, mission, lease)
        current_state = mission["state"]
        if args.to_state not in ALLOWED_TRANSITIONS[current_state]:
            raise LedgerError(
                "invalid_transition",
                f"transition {current_state} -> {args.to_state} is not allowed",
            )
        if args.to_state == "complete":
            latest_verifying_event = connection.execute(
                """
                SELECT MAX(id) FROM events
                WHERE mission_id = ?
                  AND action = 'transition'
                  AND state_to = 'verifying'
                """,
                (args.mission_id,),
            ).fetchone()[0]
            if latest_verifying_event is None:
                raise LedgerError(
                    "completion_evidence_required",
                    "latest verifying transition could not be established",
                )
            evidence_count = connection.execute(
                """
                SELECT COUNT(*) FROM events
                WHERE mission_id = ?
                  AND action = 'record'
                  AND kind = 'evidence'
                  AND id > ?
                  AND lease_generation = ?
                """,
                (args.mission_id, latest_verifying_event, lease["generation"]),
            ).fetchone()[0]
            if evidence_count < 1:
                raise LedgerError(
                    "completion_evidence_required",
                    "fresh evidence under the current lease generation is required "
                    "after the latest verifying transition",
                )

        connection.execute(
            """
            UPDATE missions
            SET state = ?, version = version + 1,
                completion_summary = ?, updated_at = ?
            WHERE id = ?
            """,
            (args.to_state, completion_summary, now, args.mission_id),
        )
        cursor = connection.execute(
            """
            INSERT INTO events (
                mission_id, action, kind, summary, payload_json, payload_hash,
                idempotency_key, state_from, state_to, lease_generation, created_at
            ) VALUES (?, 'transition', 'decision', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                args.mission_id,
                summary,
                canonical_payload,
                payload_hash(canonical_payload),
                idempotency_key,
                current_state,
                args.to_state,
                lease["generation"],
                now,
            ),
        )
        lease_released = args.to_state in LEASE_RELEASING_STATES
        if lease_released:
            connection.execute(
                "DELETE FROM leases WHERE mission_id = ?",
                (args.mission_id,),
            )
        event = connection.execute(
            "SELECT * FROM events WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        updated = require_mission(connection, args.mission_id)
        active_lease = connection.execute(
            "SELECT * FROM leases WHERE mission_id = ? AND expires_at > ?",
            (args.mission_id, time.time()),
        ).fetchone()
        return {
            "ok": True,
            "replayed": False,
            "event_effect": {"lease_released": lease_released},
            "event": event_from_row(event),
            "mission": mission_from_row(updated),
            "active_lease": (
                lease_from_row(active_lease) if active_lease is not None else None
            ),
        }


def command_release(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    owner = require_text(args.owner, "owner")
    with immediate_transaction(connection):
        wall_time = time.time()
        mission = require_mission(connection, args.mission_id)
        lease = require_current_lease(
            connection,
            args.mission_id,
            owner,
            args.lease_generation,
            wall_time,
        )
        now = logical_mutation_time(wall_time, mission, lease)
        connection.execute(
            "DELETE FROM leases WHERE mission_id = ?",
            (args.mission_id,),
        )
        connection.execute(
            "UPDATE missions SET updated_at = ? WHERE id = ?",
            (now, args.mission_id),
        )
        return {"ok": True, "released": True, "mission_id": args.mission_id}


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def positive_sqlite_int(value: str) -> int:
    parsed = positive_int(value)
    if parsed > SQLITE_INT64_MAX:
        raise argparse.ArgumentTypeError(
            f"must be no greater than SQLite's signed 64-bit maximum ({SQLITE_INT64_MAX})"
        )
    return parsed


def nonnegative_sqlite_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    if parsed > SQLITE_INT64_MAX:
        raise argparse.ArgumentTypeError(
            f"must be no greater than SQLite's signed 64-bit maximum ({SQLITE_INT64_MAX})"
        )
    return parsed


def add_owner_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--owner",
        required=True,
        help="unique identifier for this ownership execution",
    )


def add_lease_generation_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--lease-generation",
        type=positive_sqlite_int,
        required=True,
        help="generation returned by the successful claim for this execution",
    )


def add_ttl_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ttl-seconds",
        type=positive_float,
        default=DEFAULT_TTL_SECONDS,
        help=f"lease duration in seconds (default: {DEFAULT_TTL_SECONDS:g})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        description="Maintain durable local outcome contracts, evidence, and owner leases."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db_path(),
        help="SQLite path (default: ${CODEX_HOME:-~/.codex}/outcome-owner/objectives.sqlite3)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="create or idempotently recover a mission")
    start.add_argument("--objective", required=True)
    start.add_argument("--purpose", required=True)
    start.add_argument("--desired-state", required=True)
    start.add_argument("--success-criterion", action="append", required=True)
    start.add_argument("--constraint", action="append", required=True)
    start.add_argument("--repo-root", required=True)
    start.add_argument("--authority", choices=("read-only", "local-write"), required=True)
    start.add_argument("--idempotency-key", required=True)
    start.set_defaults(handler=command_start)

    list_parser = subparsers.add_parser("list", help="list mission summaries")
    list_parser.add_argument("--state", choices=MISSION_STATES)
    list_parser.add_argument("--repo-root")
    list_parser.add_argument(
        "--limit", type=positive_sqlite_int, default=DEFAULT_LIST_LIMIT
    )
    list_parser.set_defaults(handler=command_list)

    show = subparsers.add_parser("show", help="show a mission and recent reconciliation events")
    show.add_argument("mission_id")
    show.add_argument(
        "--events-limit",
        type=positive_sqlite_int,
        default=DEFAULT_EVENTS_LIMIT,
    )
    show.set_defaults(handler=command_show)

    claim = subparsers.add_parser("claim", help="claim or renew one owner lease")
    claim.add_argument("mission_id")
    add_owner_argument(claim)
    claim.add_argument(
        "--expected-generation",
        type=nonnegative_sqlite_int,
        required=True,
        help="mission lease generation last observed before this claim",
    )
    claim.add_argument(
        "--expected-version",
        type=positive_sqlite_int,
        required=True,
        help="mission version last observed before this claim",
    )
    add_ttl_argument(claim)
    claim.set_defaults(handler=command_claim)

    heartbeat = subparsers.add_parser("heartbeat", help="renew the current owner lease")
    heartbeat.add_argument("mission_id")
    add_owner_argument(heartbeat)
    add_lease_generation_argument(heartbeat)
    add_ttl_argument(heartbeat)
    heartbeat.set_defaults(handler=command_heartbeat)

    record = subparsers.add_parser("record", help="append an owner-authorized event")
    record.add_argument("mission_id")
    add_owner_argument(record)
    add_lease_generation_argument(record)
    record.add_argument("--kind", choices=EVENT_KINDS, required=True)
    record.add_argument("--summary", required=True)
    record.add_argument("--metadata-json", default="{}")
    record.add_argument("--idempotency-key", required=True)
    record.set_defaults(handler=command_record)

    transition = subparsers.add_parser("transition", help="change mission state")
    transition.add_argument("mission_id")
    add_owner_argument(transition)
    add_lease_generation_argument(transition)
    transition.add_argument("--to", dest="to_state", choices=MISSION_STATES, required=True)
    transition.add_argument("--expected-version", type=positive_int, required=True)
    transition.add_argument("--summary", required=True)
    transition.add_argument("--completion-summary")
    transition.add_argument("--idempotency-key", required=True)
    transition.set_defaults(handler=command_transition)

    release = subparsers.add_parser("release", help="release the current owner lease")
    release.add_argument("mission_id")
    add_owner_argument(release)
    add_lease_generation_argument(release)
    release.set_defaults(handler=command_release)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    old_umask = os.umask(0o077)
    connection: sqlite3.Connection | None = None
    try:
        if args.command == "start":
            repo_root = normalize_repo_root(args.repo_root)
            repo_case_sensitive: bool | None = None
            try:
                repo_stat = repo_root.stat()
            except OSError:
                pass
            else:
                if stat.S_ISDIR(repo_stat.st_mode):
                    repo_case_sensitive = filesystem_is_case_sensitive(
                        repo_root,
                        repo_stat,
                    )
            validate_database_repo_separation(
                normalize_database_path(args.db),
                ((str(repo_root), repo_case_sensitive),),
            )
            validate_preflight_repo_separation(
                preflight_workspace_root(),
                ((str(repo_root), repo_case_sensitive),),
            )
        connection = connect_database(args.db)
        result = args.handler(connection, args)
        connection.close()
        connection = None
        write_json(result)
        return 0
    except LedgerError as exc:
        write_error(exc.code, exc.message, details=exc.details)
        return 2
    except sqlite3.Error as exc:
        write_error("database_error", str(exc))
        return 3
    except (ValueError, TypeError, RecursionError, OverflowError):
        write_error("database_error", "persisted outcome ledger data is invalid")
        return 3
    except OSError as exc:
        write_error("io_error", str(exc))
        return 3
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error:
                pass
        os.umask(old_umask)


if __name__ == "__main__":
    raise SystemExit(main())
