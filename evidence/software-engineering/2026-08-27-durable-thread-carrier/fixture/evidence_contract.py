#!/usr/bin/env python3
"""Shared fail-closed contracts for frozen PR #42 evidence."""

from __future__ import annotations

from contextlib import contextmanager
import copy
from dataclasses import dataclass
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, BinaryIO, Iterator
import zlib


EVALUATION_ID = "software-engineering-durable-thread-v6-runtime-boundary"
BASELINE_COMMIT = "aa2ae97856d7968e50511864c03f1babcd608d0d"
CANDIDATE_COMMIT = "a7056f2469b1b8c6ae8cb996f4624e9c333205cd"
EXECUTION_HARNESS_SHA256 = (
    "2c5910b7870d8befe33d205dbab19a0434c211e614766034cbc15f433906417b"
)
ARTIFACT_SCOPE = "local raw evidence; publish only per-run explicit allowlists"
PRIMARY_RUN_POLICY = (
    "one fresh run per case/side; valid fail and model noncompliance are not rerun"
)
CASE_IDS = (
    "SE-BOUNDED-CHILD-CONTROL",
    "SE-DURABLE-MATCHING-REUSE",
    "SE-DURABLE-VISIBLE-CREATE",
    "SE-DURABLE-ADDRESSABILITY-RESUME",
    "SE-BINDING-MISMATCH-SAFE-FALLBACK",
    "SE-FIXED-SNAPSHOT-NON-UPGRADE",
    "SE-ACTIVE-WRITER-WAIT-REFRESH",
    "SE-DEFINITE-PREDISPATCH-FAILURE-FALLBACK",
    "SE-COMBINED-CREATE-START-AMBIGUOUS",
    "SE-POSTDISPATCH-TRANSPORT-LOSS-RECONCILE",
)

BEHAVIOR_MANIFEST_KEYS = {
    "artifact_scope",
    "baseline_commit",
    "candidate_commit",
    "evaluation_id",
    "execution_harness_sha256",
    "grading_harness_sha256",
    "primary_run_policy",
    "runs",
    "schema_version",
}
LEGACY_BEHAVIOR_MANIFEST_KEYS = BEHAVIOR_MANIFEST_KEYS - {
    "grading_harness_sha256"
}
RUN_ENTRY_KEYS = {
    "case_id",
    "side",
    "replicate",
    "run_id",
    "run_dir",
    "result_sha256",
    "raw_trace_sha256",
}
EXPECTED_PUBLISH_PATHS = {
    "addressability-handoff.json",
    "binding-observations.json",
    "carrier-contract.md",
    "carrier-thread-histories.json",
    "controller-events.jsonl",
    "final-diff.patch",
    "final-git-status.txt",
    "initial-primary-binding.json",
    "mutation-audit.json",
    "oracle.log",
    "policy/policy-load-manifest.json",
    "raw-trace.jsonl",
    "reconciliation.json",
    "result.json",
}
REQUIRED_PUBLISH_PATHS = EXPECTED_PUBLISH_PATHS - {
    "addressability-handoff.json"
}
PUBLISH_MANIFEST_PATH = "publish-manifest.json"
PUBLISH_COMPATIBILITY_SURFACE = (
    "controller-hosted app-server dynamicTools; not stock TUI E2E"
)
PUBLISH_EXPLICITLY_EXCLUDED = [
    "policy/codex-home/auth.json",
    "all other CODEX_HOME files",
    "unreviewed raw run-directory contents",
]
GRADING_HARNESS_PATHS = (
    "evidence_contract.py",
    "grade_runs.py",
    "publish_evidence.py",
)

MAX_BEHAVIOR_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_PUBLISH_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_RESULT_BYTES = 64 * 1024 * 1024
MAX_STRUCTURED_JSON_BYTES = 64 * 1024 * 1024
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_PUBLICATION_BYTES = 1280 * 1024 * 1024
MAX_JSONL_RECORD_BYTES = 8 * 1024 * 1024
MAX_JSONL_RECORDS = 100_000
MAX_STRUCTURED_NODES = 1_000_000

_SHA256 = re.compile(r"[0-9a-f]{64}")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_SENSITIVE_KEY_FOLDS = {
    "accesstoken",
    "apikey",
    "authorization",
    "clientsecret",
    "password",
    "privatekey",
    "refreshtoken",
    "secretaccesskey",
}
_TEXT_CREDENTIAL_VALUE_START = (
    rb"(?:[\"'`][ \t]*[^\s\"'`]|[A-Za-z0-9._~+/=@!#$%^&*-])"
)
_CREDENTIAL_PATTERNS = (
    re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(rb"(?i)\bBearer[ \t]+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(rb"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{16,})\b"),
    re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(
        rb"(?im)(?:^|[^A-Za-z0-9])(?:[A-Za-z0-9]+[._-])*"
        rb"(?:password|pass[_-]?phrase)[ \t]*[:=][ \t]*"
        + _TEXT_CREDENTIAL_VALUE_START
    ),
    re.compile(
        rb"(?im)\bauthorization[ \t]*[:=][ \t]*"
        rb"(?:basic|bearer|api[-_ ]?key)[ \t]+"
        + _TEXT_CREDENTIAL_VALUE_START
    ),
    re.compile(
        rb"(?im)\b(?:x[-_])?api[-_ ]?key[ \t]*[:=][ \t]*"
        + _TEXT_CREDENTIAL_VALUE_START
    ),
    re.compile(
        rb"(?i)(?:access[_-]?token|refresh[_-]?token|api[_-]?key|"
        rb"client[_-]?secret|private[_-]?key|secret[_-]?access[_-]?key)"
        rb"[ \t\"']*[:=][ \t\"']*[A-Za-z0-9._~+/=-]{16,}"
    ),
)
_OPEN_DIRECTORY_FLAGS = (
    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
)
_OPEN_FILE_FLAGS = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW


class PublicationError(ValueError):
    """An evidence or publication contract could not be proven."""


def canonical_relative_path(raw: Any) -> str:
    """Return one exact portable artifact path or raise fail closed."""
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise PublicationError("publication path is not a portable relative string")
    relative = PurePosixPath(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise PublicationError(f"publication path is not canonical relative: {raw}")
    if str(relative) != raw:
        raise PublicationError(f"publication path is not canonical relative: {raw}")
    return raw


def behavior_manifest_invalid_reasons(
    manifest: Any,
    *,
    expected_grading_harness_sha256: str | None = None,
    allow_unbound: bool = False,
) -> list[str]:
    """Validate the complete immutable 10-case baseline/candidate inventory."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["run manifest is not an object"]
    manifest_keys = set(manifest)
    allowed_keys = {frozenset(BEHAVIOR_MANIFEST_KEYS)}
    if allow_unbound:
        allowed_keys.add(frozenset(LEGACY_BEHAVIOR_MANIFEST_KEYS))
    if frozenset(manifest_keys) not in allowed_keys:
        errors.append("run manifest top-level fields are not exact")
    expected_scalars = {
        "schema_version": 6,
        "evaluation_id": EVALUATION_ID,
        "artifact_scope": ARTIFACT_SCOPE,
        "baseline_commit": BASELINE_COMMIT,
        "candidate_commit": CANDIDATE_COMMIT,
        "execution_harness_sha256": EXECUTION_HARNESS_SHA256,
        "primary_run_policy": PRIMARY_RUN_POLICY,
    }
    for field, expected in expected_scalars.items():
        if manifest.get(field) != expected:
            errors.append(f"run manifest {field} mismatch")
    grading_sha256 = manifest.get("grading_harness_sha256")
    if "grading_harness_sha256" not in manifest and allow_unbound:
        pass
    elif not isinstance(grading_sha256, str) or _SHA256.fullmatch(
        grading_sha256
    ) is None:
        errors.append("run manifest grading_harness_sha256 is invalid")
    elif (
        expected_grading_harness_sha256 is not None
        and grading_sha256 != expected_grading_harness_sha256
    ):
        errors.append("run manifest grading_harness_sha256 mismatch")
    runs = manifest.get("runs")
    if not isinstance(runs, list):
        return sorted(set(errors + ["run manifest run inventory is not a list"]))
    if len(runs) != len(CASE_IDS) * 2:
        errors.append("run manifest does not contain exactly 20 primary runs")
    observed: list[tuple[Any, Any]] = []
    run_ids: list[str] = []
    run_dirs: list[str] = []
    for index, entry in enumerate(runs):
        if not isinstance(entry, dict):
            errors.append(f"run manifest entry {index} is not an object")
            continue
        if set(entry) != RUN_ENTRY_KEYS:
            errors.append(f"run manifest entry fields are not exact: {index}")
        case_id = entry.get("case_id")
        side = entry.get("side")
        observed.append((case_id, side))
        if case_id not in CASE_IDS:
            errors.append(f"run manifest case ID is invalid: {index}")
        if not isinstance(side, str) or side not in {"baseline", "candidate"}:
            errors.append(f"run manifest side is invalid: {index}")
        if entry.get("replicate") != "primary":
            errors.append(f"run manifest replicate is not primary: {index}")
        run_id = entry.get("run_id")
        if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
            errors.append(f"run manifest run ID is invalid: {index}")
        else:
            run_ids.append(run_id)
        run_dir = entry.get("run_dir")
        if not isinstance(run_dir, str) or not run_dir:
            errors.append(f"run manifest run directory is invalid: {index}")
        else:
            run_dirs.append(run_dir)
        for field in ("result_sha256", "raw_trace_sha256"):
            value = entry.get(field)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                errors.append(f"run manifest {field} is invalid: {index}")
    expected = [(case, side) for case in CASE_IDS for side in ("baseline", "candidate")]
    if sorted(observed, key=repr) != sorted(expected, key=repr):
        errors.append("manifest does not contain exactly one primary run per case/side")
    if len(run_ids) != len(set(run_ids)):
        errors.append("run manifest run IDs are reused")
    if len(run_dirs) != len(set(run_dirs)):
        errors.append("run manifest run directories are reused")
    return sorted(set(errors))


def bind_behavior_manifest(
    manifest: Any,
    *,
    source_manifest_path: Path,
    grading_harness_sha256: str,
) -> dict[str, Any]:
    """Return a portable-copy manifest bound to the current grading semantics."""
    errors = behavior_manifest_invalid_reasons(
        manifest,
        expected_grading_harness_sha256=grading_harness_sha256,
        allow_unbound=True,
    )
    if errors:
        raise PublicationError("; ".join(errors))
    if not isinstance(grading_harness_sha256, str) or _SHA256.fullmatch(
        grading_harness_sha256
    ) is None:
        raise PublicationError("grading harness aggregate is invalid")
    bound = copy.deepcopy(manifest)
    absolute_manifest = Path(
        os.path.abspath(os.fspath(source_manifest_path.expanduser()))
    )
    for entry in bound["runs"]:
        raw_run_dir = Path(entry["run_dir"]).expanduser()
        if not raw_run_dir.is_absolute():
            raw_run_dir = absolute_manifest.parent / raw_run_dir
        entry["run_dir"] = os.path.abspath(os.fspath(raw_run_dir))
    bound["grading_harness_sha256"] = grading_harness_sha256
    bound_errors = behavior_manifest_invalid_reasons(
        bound,
        expected_grading_harness_sha256=grading_harness_sha256,
    )
    if bound_errors:
        raise PublicationError("; ".join(bound_errors))
    return bound


def publication_inventory_invalid_reasons(
    publish: Any,
    case_id: str | None,
    *,
    require_case_artifacts: bool = True,
) -> list[str]:
    """Validate one exact per-run publication inventory without opening artifacts."""
    reasons: list[str] = []
    if not isinstance(publish, dict):
        return ["publication allowlist is not an object"]
    if set(publish) != {
        "compatibility_surface",
        "explicitly_excluded",
        "files",
        "publication_mode",
        "schema_version",
    }:
        reasons.append("publication manifest fields are not exact")
    if publish.get("schema_version") != 1:
        reasons.append("publication schema is not v1")
    if publish.get("publication_mode") != "explicit allowlist only":
        reasons.append("publication mode is not explicit allowlist")
    if publish.get("compatibility_surface") != PUBLISH_COMPATIBILITY_SURFACE:
        reasons.append("publication compatibility surface mismatch")
    if publish.get("explicitly_excluded") != PUBLISH_EXPLICITLY_EXCLUDED:
        reasons.append("publication exclusion inventory mismatch")
    entries = publish.get("files")
    if not isinstance(entries, list):
        return sorted(set(reasons + ["publication file inventory is not a list"]))
    seen: set[str] = set()
    declared_total = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            reasons.append(f"publication entry is not an object: {index}")
            continue
        if set(entry) != {"path", "sha256", "size_bytes"}:
            reasons.append(f"publication entry fields are not exact: {index}")
        try:
            relative = canonical_relative_path(entry.get("path"))
        except PublicationError as exc:
            reasons.append(str(exc))
            continue
        if relative in seen:
            reasons.append(f"publication path is duplicated: {relative}")
            continue
        seen.add(relative)
        if relative not in EXPECTED_PUBLISH_PATHS:
            reasons.append(f"publication path is not allowlisted: {relative}")
        size = entry.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            reasons.append(f"published artifact size is invalid: {relative}")
        elif size > MAX_ARTIFACT_BYTES:
            reasons.append(f"published artifact exceeds hard size limit: {relative}")
        else:
            declared_total += size
        digest = entry.get("sha256")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            reasons.append(f"published artifact hash is invalid: {relative}")
    for relative in sorted(REQUIRED_PUBLISH_PATHS - seen):
        reasons.append(f"required published artifact is missing: {relative}")
    if require_case_artifacts and case_id == "SE-DURABLE-ADDRESSABILITY-RESUME" and (
        "addressability-handoff.json" not in seen
    ):
        reasons.append("addressability handoff is missing from publication allowlist")
    if declared_total > MAX_PUBLICATION_BYTES:
        reasons.append("publication inventory exceeds global hard size limit")
    return sorted(set(reasons))


def publication_entries(publish: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return a validated path-indexed publication inventory."""
    invalid = publication_inventory_invalid_reasons(
        publish, None, require_case_artifacts=False
    )
    if invalid:
        raise PublicationError("; ".join(invalid))
    return {entry["path"]: entry for entry in publish["files"]}


@contextmanager
def open_directory_fd(path: Path) -> Iterator[tuple[int, Path]]:
    """Open an absolute directory component-by-component without following links."""
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    fd = os.open("/", _OPEN_DIRECTORY_FLAGS)
    try:
        for part in absolute.parts[1:]:
            next_fd = os.open(part, _OPEN_DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise PublicationError(f"path is not a directory: {absolute}")
        yield fd, absolute
    except OSError as exc:
        raise PublicationError(f"directory path is unavailable or symbolic: {absolute}") from exc
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _open_relative_file(root_fd: int, relative: str) -> int:
    parts = PurePosixPath(canonical_relative_path(relative)).parts
    directory_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, _OPEN_DIRECTORY_FLAGS, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        fd = os.open(parts[-1], _OPEN_FILE_FLAGS, dir_fd=directory_fd)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise PublicationError(
            f"published artifact is unavailable or symbolic: {relative}"
        ) from exc
    finally:
        os.close(directory_fd)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise PublicationError(f"published artifact is not a regular file: {relative}")
    return fd


@dataclass
class ArtifactRoot:
    fd: int
    path: Path
    initial_stat: os.stat_result

    @property
    def identity(self) -> tuple[int, int]:
        return (self.initial_stat.st_dev, self.initial_stat.st_ino)


@contextmanager
def open_artifact_root(run_dir: Path) -> Iterator[ArtifactRoot]:
    """Hold one run-directory fd for every artifact in that run."""
    with open_directory_fd(run_dir) as (root_fd, absolute):
        initial = os.fstat(root_fd)
        root = ArtifactRoot(root_fd, absolute, initial)
        yield root
        final = os.fstat(root_fd)
        if (initial.st_dev, initial.st_ino) != (final.st_dev, final.st_ino):
            raise PublicationError(f"artifact root identity changed: {absolute}")


@dataclass
class OpenedArtifact:
    fd: int
    compressed: bool
    relative: str
    initial_stat: os.stat_result


def open_artifact_fd(
    run_dir: Path | ArtifactRoot, relative_raw: Any
) -> OpenedArtifact:
    """Open exactly one plain or gzip artifact beneath a stable nofollow root fd."""
    relative = canonical_relative_path(relative_raw)
    @contextmanager
    def selected_root() -> Iterator[int]:
        if isinstance(run_dir, ArtifactRoot):
            yield run_dir.fd
        else:
            with open_directory_fd(run_dir) as (root_fd, _absolute):
                yield root_fd

    with selected_root() as root_fd:
        opened: list[tuple[int, bool]] = []
        for candidate, compressed in ((relative, False), (f"{relative}.gz", True)):
            try:
                fd = _open_relative_file(root_fd, candidate)
            except FileNotFoundError:
                continue
            opened.append((fd, compressed))
        if len(opened) != 1:
            for fd, _compressed in opened:
                os.close(fd)
            if opened:
                raise PublicationError(
                    f"artifact has ambiguous plain and gzip forms: {relative}"
                )
            raise PublicationError(f"published artifact is missing: {relative}")
        fd, compressed = opened[0]
        return OpenedArtifact(fd, compressed, relative, os.fstat(fd))


def _stable_signature(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


@contextmanager
def open_artifact_binary(
    run_dir: Path | ArtifactRoot, relative: Any
) -> Iterator[BinaryIO]:
    """Yield one stable plain/decompressed stream backed by a nofollow fd."""
    opened = open_artifact_fd(run_dir, relative)
    raw = os.fdopen(opened.fd, "rb", closefd=True)
    stream: BinaryIO = raw
    if opened.compressed:
        stream = gzip.GzipFile(fileobj=raw, mode="rb")
    try:
        yield stream
    except (EOFError, gzip.BadGzipFile, OSError, zlib.error) as exc:
        raise PublicationError(f"artifact is unreadable: {opened.relative}") from exc
    finally:
        if stream is not raw:
            stream.close()
        try:
            final_stat = os.fstat(raw.fileno())
        except OSError:
            final_stat = None
        raw.close()
        if final_stat is not None and _stable_signature(final_stat) != _stable_signature(
            opened.initial_stat
        ):
            raise PublicationError(
                f"artifact changed while being read: {opened.relative}"
            )


def iter_artifact_chunks(
    run_dir: Path | ArtifactRoot,
    relative: Any,
    *,
    max_bytes: int = MAX_ARTIFACT_BYTES,
    expected_size: int | None = None,
) -> Iterator[bytes]:
    observed = 0
    with open_artifact_binary(run_dir, relative) as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > max_bytes:
                raise PublicationError(f"artifact exceeds hard size limit: {relative}")
            if expected_size is not None and observed > expected_size:
                raise PublicationError(f"published artifact size mismatch: {relative}")
            yield chunk
    if expected_size is not None and observed != expected_size:
        raise PublicationError(f"published artifact size mismatch: {relative}")


def artifact_measure(
    run_dir: Path | ArtifactRoot,
    relative: Any,
    *,
    max_bytes: int = MAX_ARTIFACT_BYTES,
    expected_size: int | None = None,
) -> tuple[int, str]:
    size = 0
    digest = hashlib.sha256()
    for chunk in iter_artifact_chunks(
        run_dir, relative, max_bytes=max_bytes, expected_size=expected_size
    ):
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def read_artifact_bytes(
    run_dir: Path | ArtifactRoot,
    relative: Any,
    *,
    max_bytes: int = MAX_ARTIFACT_BYTES,
    expected_size: int | None = None,
) -> bytes:
    return b"".join(
        iter_artifact_chunks(
            run_dir, relative, max_bytes=max_bytes, expected_size=expected_size
        )
    )


def strict_json_loads(payload: bytes | str, *, description: str) -> Any:
    """Parse standards-compliant JSON while rejecting ambiguous object meaning."""

    def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, nested in pairs:
            if key in value:
                raise PublicationError(
                    f"{description} contains a duplicate object key"
                )
            value[key] = nested
        return value

    def reject_nonfinite(_constant: str) -> Any:
        raise PublicationError(f"{description} contains a non-finite number")

    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_pairs,
            parse_constant=reject_nonfinite,
        )
    except PublicationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise PublicationError(f"{description} is not valid UTF-8 JSON") from exc


def read_artifact_json(
    run_dir: Path | ArtifactRoot,
    relative: Any,
    *,
    max_bytes: int = MAX_RESULT_BYTES,
    expected_size: int | None = None,
) -> Any:
    return strict_json_loads(
        read_artifact_bytes(
            run_dir,
            relative,
            max_bytes=max_bytes,
            expected_size=expected_size,
        ),
        description=f"artifact {relative}",
    )


def read_path_bytes_no_symlink(path: Path, *, max_bytes: int) -> bytes:
    """Read one regular path through nofollow fds with a finite bound."""
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    try:
        with open_directory_fd(absolute.parent) as (parent_fd, _parent):
            fd = _open_relative_file(parent_fd, absolute.name)
    except PublicationError:
        raise
    except OSError as exc:
        raise PublicationError(f"file is unavailable or symbolic: {absolute}") from exc
    initial = os.fstat(fd)
    chunks: list[bytes] = []
    observed = 0
    try:
        with os.fdopen(fd, "rb", closefd=True) as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                observed += len(chunk)
                if observed > max_bytes:
                    raise PublicationError(f"file exceeds hard size limit: {absolute}")
                chunks.append(chunk)
            final = os.fstat(handle.fileno())
    except OSError as exc:
        raise PublicationError(f"file is unreadable: {absolute}") from exc
    if _stable_signature(initial) != _stable_signature(final):
        raise PublicationError(f"file changed while being read: {absolute}")
    return b"".join(chunks)


def read_path_json_no_symlink(path: Path, *, max_bytes: int) -> Any:
    return strict_json_loads(
        read_path_bytes_no_symlink(path, max_bytes=max_bytes),
        description=f"file {path}",
    )


def iter_artifact_jsonl(
    run_dir: Path | ArtifactRoot,
    relative: str,
    *,
    expected_size: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Parse bounded JSONL without ever allocating an unbounded line."""
    observed = 0
    physical_records = 0
    with open_artifact_binary(run_dir, relative) as handle:
        while True:
            line = handle.readline(MAX_JSONL_RECORD_BYTES + 1)
            if not line:
                break
            physical_records += 1
            if physical_records > MAX_JSONL_RECORDS:
                raise PublicationError(
                    f"JSONL record count exceeds hard limit: {relative}"
                )
            observed += len(line)
            if len(line) > MAX_JSONL_RECORD_BYTES:
                raise PublicationError(f"JSONL record exceeds hard size limit: {relative}")
            if observed > MAX_ARTIFACT_BYTES:
                raise PublicationError(f"artifact exceeds hard size limit: {relative}")
            if expected_size is not None and observed > expected_size:
                raise PublicationError(f"published artifact size mismatch: {relative}")
            if not line.strip():
                continue
            value = strict_json_loads(
                line,
                description=f"JSONL artifact {relative}",
            )
            if not isinstance(value, dict):
                raise PublicationError(f"JSONL record is not an object: {relative}")
            yield value
    if expected_size is not None and observed != expected_size:
        raise PublicationError(f"published artifact size mismatch: {relative}")


def structured_credential_present(value: Any) -> bool:
    """Find structured secrets and credential syntax in decoded string values."""
    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > MAX_STRUCTURED_NODES:
            raise PublicationError("structured artifact exceeds node limit")
        if isinstance(current, dict):
            for key, nested in current.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if normalized in _SENSITIVE_KEY_FOLDS and nested not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    return True
                stack.append(nested)
        elif isinstance(current, list):
            stack.extend(current)
        elif isinstance(current, str) and credential_pattern_present(
            current.encode("utf-8", errors="surrogatepass")
        ):
            return True
    return False


def credential_pattern_present(payload: bytes) -> bool:
    return any(pattern.search(payload) is not None for pattern in _CREDENTIAL_PATTERNS)


def publication_invalid_reasons(
    run_dir: Path | ArtifactRoot,
    publish: Any,
    case_id: str | None,
    *,
    require_case_artifacts: bool = True,
) -> list[str]:
    """Validate inventory plus exact bounded decompressed source bytes."""
    reasons = publication_inventory_invalid_reasons(
        publish, case_id, require_case_artifacts=require_case_artifacts
    )
    if reasons or not isinstance(publish, dict):
        return reasons
    for entry in publish["files"]:
        relative = entry["path"]
        try:
            size, digest = artifact_measure(
                run_dir, relative, expected_size=entry["size_bytes"]
            )
        except PublicationError as exc:
            reasons.append(str(exc))
            continue
        if size != entry["size_bytes"]:
            reasons.append(f"published artifact size mismatch: {relative}")
        if digest != entry["sha256"]:
            reasons.append(f"published artifact hash mismatch: {relative}")
    return sorted(set(reasons))


def compute_grading_harness_identity(
    fixture_dir: Path | None = None,
) -> dict[str, Any]:
    """Hash every tracked file that can change grading/publication meaning."""
    root = Path(__file__).resolve().parent if fixture_dir is None else fixture_dir
    files: list[dict[str, Any]] = []
    for relative in GRADING_HARNESS_PATHS:
        payload = read_path_bytes_no_symlink(root / relative, max_bytes=8 * 1024 * 1024)
        files.append(
            {
                "path": relative,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    encoded = json.dumps(
        files, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "path_base": "fixture",
        "files": files,
        "grading_harness_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def grading_harness_identity_errors(identity: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(identity, dict):
        return ["grading harness identity is not an object"]
    if set(identity) != {
        "schema_version",
        "path_base",
        "files",
        "grading_harness_sha256",
    }:
        errors.append("grading harness identity fields are not exact")
    if identity.get("schema_version") != 1 or identity.get("path_base") != "fixture":
        errors.append("grading harness identity metadata mismatch")
    files = identity.get("files")
    if not isinstance(files, list):
        return sorted(set(errors + ["grading harness file inventory is not a list"]))
    paths: list[Any] = []
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "sha256",
            "size_bytes",
        }:
            errors.append("grading harness file entry is invalid")
            continue
        paths.append(entry.get("path"))
        if not isinstance(entry.get("size_bytes"), int) or isinstance(
            entry.get("size_bytes"), bool
        ):
            errors.append("grading harness file size is invalid")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            errors.append("grading harness file hash is invalid")
    if tuple(paths) != GRADING_HARNESS_PATHS:
        errors.append("grading harness file inventory mismatch")
    encoded = json.dumps(
        files, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    if identity.get("grading_harness_sha256") != hashlib.sha256(encoded).hexdigest():
        errors.append("grading harness aggregate mismatch")
    return sorted(set(errors))
