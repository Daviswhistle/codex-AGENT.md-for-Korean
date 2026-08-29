#!/usr/bin/env python3
"""Atomically publish only frozen, allowlisted PR #42 evidence."""

from __future__ import annotations

import argparse
import ctypes
import errno
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
from typing import Any, BinaryIO

from evidence_contract import ArtifactRoot
from evidence_contract import artifact_measure
from evidence_contract import bind_behavior_manifest
from evidence_contract import canonical_relative_path
from evidence_contract import compute_grading_harness_identity
from evidence_contract import credential_pattern_present
from evidence_contract import EXPECTED_PUBLISH_PATHS
from evidence_contract import grading_harness_identity_errors
from evidence_contract import iter_artifact_chunks
from evidence_contract import MAX_ARTIFACT_BYTES
from evidence_contract import MAX_BEHAVIOR_MANIFEST_BYTES
from evidence_contract import MAX_JSONL_RECORD_BYTES
from evidence_contract import MAX_JSONL_RECORDS
from evidence_contract import MAX_PUBLICATION_BYTES
from evidence_contract import MAX_PUBLISH_MANIFEST_BYTES
from evidence_contract import MAX_STRUCTURED_JSON_BYTES
from evidence_contract import open_artifact_binary
from evidence_contract import open_artifact_fd
from evidence_contract import open_artifact_root
from evidence_contract import open_directory_fd
from evidence_contract import PUBLISH_MANIFEST_PATH
from evidence_contract import PublicationError
from evidence_contract import publication_entries
from evidence_contract import publication_invalid_reasons
from evidence_contract import publication_inventory_invalid_reasons
from evidence_contract import read_artifact_bytes
from evidence_contract import read_path_bytes_no_symlink
from evidence_contract import structured_credential_present
from evidence_contract import strict_json_loads


_RENAME_NOREPLACE = 1
_MAX_STAGED_STORAGE_BYTES = MAX_ARTIFACT_BYTES + 16 * 1024 * 1024


def _safe_run_dir(manifest_path: Path, raw: str) -> Path:
    run_dir = Path(raw).expanduser()
    return run_dir if run_dir.is_absolute() else manifest_path.parent / run_dir


def _mkdirs_at(root_fd: int, relative_parent: str) -> int:
    current_fd = os.dup(root_fd)
    try:
        if not relative_parent:
            return current_fd
        for part in PurePosixPath(relative_parent).parts:
            try:
                os.mkdir(part, mode=0o755, dir_fd=current_fd)
            except FileExistsError:
                pass
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _open_destination_exclusive(root_fd: int, relative: str) -> BinaryIO:
    canonical = canonical_relative_path(relative)
    parent = PurePosixPath(canonical).parent.as_posix()
    if parent == ".":
        parent = ""
    directory_fd = _mkdirs_at(root_fd, parent)
    try:
        fd = os.open(
            PurePosixPath(canonical).name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o644,
            dir_fd=directory_fd,
        )
    except OSError as exc:
        raise PublicationError(
            f"publication destination is not exclusively creatable: {canonical}"
        ) from exc
    finally:
        os.close(directory_fd)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise PublicationError(f"publication destination is not regular: {canonical}")
    return os.fdopen(fd, "wb", closefd=True)


def _remember_staged_artifact(
    expectations: dict[str, dict[str, Any]],
    staging_root: ArtifactRoot,
    logical_path: str,
    *,
    compressed: bool,
    size_bytes: int,
    sha256: str,
) -> None:
    """Record exact stored and uncompressed identities for final verification."""
    storage_path = f"{logical_path}.gz" if compressed else logical_path
    if storage_path in expectations:
        raise PublicationError(f"staged artifact identity is duplicated: {storage_path}")
    storage_size, storage_sha256 = artifact_measure(
        staging_root,
        storage_path,
        max_bytes=_MAX_STAGED_STORAGE_BYTES,
    )
    expectations[storage_path] = {
        "logical_path": logical_path,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "storage_size_bytes": storage_size,
        "storage_sha256": storage_sha256,
    }


def _verify_staged_artifacts(
    staging_root: ArtifactRoot,
    expectations: dict[str, dict[str, Any]],
) -> None:
    """Reopen and verify every staged file after the final inventory walk."""
    for storage_path, expected in sorted(expectations.items()):
        try:
            storage_size, storage_sha256 = artifact_measure(
                staging_root,
                storage_path,
                max_bytes=expected["storage_size_bytes"],
                expected_size=expected["storage_size_bytes"],
            )
            size, sha256 = artifact_measure(
                staging_root,
                expected["logical_path"],
                max_bytes=expected["size_bytes"],
                expected_size=expected["size_bytes"],
            )
        except PublicationError as exc:
            raise PublicationError(
                f"final staged artifact verification failed: {storage_path}"
            ) from exc
        if (
            storage_size != expected["storage_size_bytes"]
            or storage_sha256 != expected["storage_sha256"]
            or size != expected["size_bytes"]
            or sha256 != expected["sha256"]
        ):
            raise PublicationError(
                f"final staged artifact verification failed: {storage_path}"
            )


def _write_deterministic_gzip_bytes(
    staging_root: ArtifactRoot, relative: str, payload: bytes
) -> None:
    with _open_destination_exclusive(staging_root.fd, f"{relative}.gz") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0
        ) as compressed:
            compressed.write(payload)
        raw.flush()
        os.fsync(raw.fileno())
    size, digest = artifact_measure(
        staging_root, relative, expected_size=len(payload)
    )
    if size != len(payload) or digest != hashlib.sha256(payload).hexdigest():
        raise PublicationError(f"staged gzip verification failed: {relative}")


def _credential_check_json(payload: bytes, relative: str) -> Any:
    value = strict_json_loads(
        payload,
        description=f"credential-scanned artifact {relative}",
    )
    if structured_credential_present(value) or credential_pattern_present(payload):
        raise PublicationError(f"credential-like content detected: {relative}")
    return value


def _copy_checked_artifact(
    source_run_dir: ArtifactRoot,
    relative: str,
    entry: dict[str, Any],
    staging_root: ArtifactRoot,
    destination_relative: str,
) -> tuple[int, str]:
    """Validate, scan, hash, and gzip the same stable source fd stream."""
    declared_size = entry["size_bytes"]
    declared_hash = entry["sha256"]
    observed = 0
    digest = hashlib.sha256()
    scanner_tail = b""
    with _open_destination_exclusive(
        staging_root.fd, f"{destination_relative}.gz"
    ) as raw_destination:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_destination,
            compresslevel=9,
            mtime=0,
        ) as compressed:
            if relative.endswith(".json"):
                payload = read_artifact_bytes(
                    source_run_dir,
                    relative,
                    max_bytes=min(MAX_STRUCTURED_JSON_BYTES, MAX_ARTIFACT_BYTES),
                    expected_size=declared_size,
                )
                _credential_check_json(payload, relative)
                observed = len(payload)
                digest.update(payload)
                compressed.write(payload)
            elif relative.endswith(".jsonl"):
                physical_records = 0
                with open_artifact_binary(source_run_dir, relative) as source:
                    while True:
                        line = source.readline(MAX_JSONL_RECORD_BYTES + 1)
                        if not line:
                            break
                        physical_records += 1
                        if physical_records > MAX_JSONL_RECORDS:
                            raise PublicationError(
                                f"JSONL record count exceeds hard limit: {relative}"
                            )
                        if len(line) > MAX_JSONL_RECORD_BYTES:
                            raise PublicationError(
                                f"JSONL record exceeds hard size limit: {relative}"
                            )
                        observed += len(line)
                        if observed > declared_size or observed > MAX_ARTIFACT_BYTES:
                            raise PublicationError(
                                f"published artifact size mismatch: {relative}"
                            )
                        record = strict_json_loads(
                            line,
                            description=f"credential-scanned JSONL artifact {relative}",
                        )
                        if not isinstance(record, dict):
                            raise PublicationError(
                                f"credential-scanned JSONL record is not an object: {relative}"
                            )
                        if structured_credential_present(record) or credential_pattern_present(
                            line
                        ):
                            raise PublicationError(
                                f"credential-like content detected: {relative}"
                            )
                        digest.update(line)
                        compressed.write(line)
            else:
                for chunk in iter_artifact_chunks(
                    source_run_dir,
                    relative,
                    expected_size=declared_size,
                ):
                    observed += len(chunk)
                    digest.update(chunk)
                    scan_window = scanner_tail + chunk
                    if credential_pattern_present(scan_window):
                        raise PublicationError(
                            f"credential-like content detected: {relative}"
                        )
                    scanner_tail = scan_window[-512:]
                    compressed.write(chunk)
        raw_destination.flush()
        os.fsync(raw_destination.fileno())
    if observed != declared_size:
        raise PublicationError(f"published artifact size mismatch: {relative}")
    observed_hash = digest.hexdigest()
    if observed_hash != declared_hash:
        raise PublicationError(f"published artifact hash mismatch: {relative}")
    staged_size, staged_hash = artifact_measure(
        staging_root,
        destination_relative,
        expected_size=declared_size,
    )
    if staged_size != declared_size or staged_hash != declared_hash:
        raise PublicationError(f"staged gzip verification failed: {destination_relative}")
    return observed, observed_hash


def _remove_tree_at(parent_fd: int, name: str) -> None:
    """Remove a private staging tree without following inserted symlinks."""
    try:
        directory_fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return
    try:
        for child in os.listdir(directory_fd):
            try:
                os.unlink(child, dir_fd=directory_fd)
            except IsADirectoryError:
                _remove_tree_at(directory_fd, child)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    os.rmdir(name, dir_fd=parent_fd)


def _rename_noreplace(parent_fd: int, source: str, destination: str) -> None:
    """Atomically publish staging without replacing any destination."""
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise PublicationError("atomic no-replace publication is unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        parent_fd,
        os.fsencode(source),
        parent_fd,
        os.fsencode(destination),
        _RENAME_NOREPLACE,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error in {errno.EEXIST, errno.ENOTEMPTY}:
            raise PublicationError("publication output already exists")
        raise PublicationError(f"atomic no-replace publication failed: errno {error}")


def _new_staging(parent_fd: int, output_name: str) -> tuple[str, int]:
    for _attempt in range(32):
        name = f".{output_name}.staging-{secrets.token_hex(8)}"
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        return name, fd
    raise PublicationError("could not allocate an exclusive publication staging tree")


def _inventory_files(staging_fd: int) -> set[str]:
    observed: set[str] = set()
    stack: list[tuple[int, str]] = [(os.dup(staging_fd), "")]
    while stack:
        directory_fd, prefix = stack.pop()
        try:
            for child in os.listdir(directory_fd):
                child_path = f"{prefix}/{child}" if prefix else child
                child_stat = os.stat(child, dir_fd=directory_fd, follow_symlinks=False)
                if stat.S_ISLNK(child_stat.st_mode):
                    raise PublicationError("publication staging contains a symlink")
                if stat.S_ISDIR(child_stat.st_mode):
                    child_fd = os.open(
                        child,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    stack.append((child_fd, child_path))
                elif stat.S_ISREG(child_stat.st_mode):
                    observed.add(child_path)
                else:
                    raise PublicationError(
                        "publication staging contains a non-regular file"
                    )
        finally:
            os.close(directory_fd)
    return observed


def _verified_grading_identity(
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = compute_grading_harness_identity() if identity is None else identity
    errors = grading_harness_identity_errors(identity)
    if errors:
        raise PublicationError("; ".join(errors))
    return identity


def _load_bound_behavior_manifest(
    manifest_path: Path, grading_harness_sha256: str
) -> tuple[Path, dict[str, Any]]:
    absolute_path = Path(
        os.path.abspath(os.fspath(manifest_path.expanduser()))
    )
    manifest_bytes = read_path_bytes_no_symlink(
        absolute_path, max_bytes=MAX_BEHAVIOR_MANIFEST_BYTES
    )
    manifest = _credential_check_json(
        manifest_bytes, "behavior-run-manifest.json"
    )
    bound = bind_behavior_manifest(
        manifest,
        source_manifest_path=absolute_path,
        grading_harness_sha256=grading_harness_sha256,
    )
    return absolute_path, bound


def _encode_behavior_manifest(manifest: dict[str, Any]) -> bytes:
    return (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def bind_behavior_manifest_file(
    manifest_path: Path,
    output_path: Path,
    *,
    grading_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one current-identity manifest atomically without changing raw evidence."""
    grading_identity = _verified_grading_identity(grading_identity)
    grading_sha256 = grading_identity["grading_harness_sha256"]
    _absolute_source, bound = _load_bound_behavior_manifest(
        manifest_path, grading_sha256
    )
    encoded = _encode_behavior_manifest(bound)
    if len(encoded) > MAX_BEHAVIOR_MANIFEST_BYTES:
        raise PublicationError("bound behavior manifest exceeds hard size limit")

    absolute_output = Path(
        os.path.abspath(os.fspath(output_path.expanduser()))
    )
    output_name = absolute_output.name
    if not output_name or output_name in {".", ".."}:
        raise PublicationError("bound manifest output name is invalid")
    with open_directory_fd(absolute_output.parent) as (parent_fd, absolute_parent):
        temporary_name: str | None = None
        temporary_fd = -1
        try:
            for _attempt in range(32):
                candidate = f".{output_name}.binding-{secrets.token_hex(8)}"
                try:
                    temporary_fd = os.open(
                        candidate,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | os.O_CLOEXEC
                        | os.O_NOFOLLOW,
                        0o644,
                        dir_fd=parent_fd,
                    )
                except FileExistsError:
                    continue
                temporary_name = candidate
                break
            if temporary_name is None or temporary_fd < 0:
                raise PublicationError(
                    "could not allocate an exclusive bound-manifest staging file"
                )
            with os.fdopen(temporary_fd, "wb", closefd=True) as destination:
                temporary_fd = -1
                destination.write(encoded)
                destination.flush()
                os.fsync(destination.fileno())
            _rename_noreplace(parent_fd, temporary_name, output_name)
            temporary_name = None
            os.fsync(parent_fd)
        finally:
            if temporary_fd >= 0:
                os.close(temporary_fd)
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
    return {
        "manifest": str(absolute_parent / output_name),
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "grading_harness_identity": grading_identity,
    }


def publish_behavior_manifest(
    manifest_path: Path,
    output_dir: Path,
    *,
    grading_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish a fully validated clone-regradable tree with atomic visibility."""
    grading_identity = _verified_grading_identity(grading_identity)
    grading_sha256 = grading_identity["grading_harness_sha256"]
    manifest_path, manifest = _load_bound_behavior_manifest(
        manifest_path, grading_sha256
    )

    output_dir = Path(os.path.abspath(os.fspath(output_dir.expanduser())))
    output_name = output_dir.name
    if not output_name or output_name in {".", ".."}:
        raise PublicationError("publication output name is invalid")
    with open_directory_fd(output_dir.parent) as (parent_fd, absolute_parent):
        try:
            existing_fd = os.open(
                output_name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise PublicationError("publication output is unavailable or symbolic") from exc
        else:
            os.close(existing_fd)
            raise PublicationError("publication output already exists")

        staging_name, staging_fd = _new_staging(parent_fd, output_name)
        published = False
        try:
            staging_root = ArtifactRoot(
                staging_fd,
                absolute_parent / staging_name,
                os.fstat(staging_fd),
            )
            published_manifest = json.loads(json.dumps(manifest))
            staged_expectations: dict[str, dict[str, Any]] = {}
            global_bytes = 0
            source_identities: set[tuple[int, int]] = set()
            for index, (source_entry, published_entry) in enumerate(
                zip(manifest["runs"], published_manifest["runs"], strict=True)
            ):
                run_id = source_entry["run_id"]
                source_run_dir = _safe_run_dir(manifest_path, source_entry["run_dir"])
                with open_artifact_root(source_run_dir) as source_root:
                    if source_root.identity in source_identities:
                        raise PublicationError(
                            f"{run_id}: source run directory identity is reused"
                        )
                    source_identities.add(source_root.identity)
                    publish_bytes = read_artifact_bytes(
                        source_root,
                        PUBLISH_MANIFEST_PATH,
                        max_bytes=MAX_PUBLISH_MANIFEST_BYTES,
                    )
                    publish = _credential_check_json(
                        publish_bytes, PUBLISH_MANIFEST_PATH
                    )
                    inventory_errors = publication_inventory_invalid_reasons(
                        publish,
                        source_entry["case_id"],
                        require_case_artifacts=False,
                    )
                    if inventory_errors:
                        raise PublicationError(
                            f"{run_id}: {'; '.join(inventory_errors)}"
                        )
                    entries = publication_entries(publish)
                    if entries["result.json"]["sha256"] != source_entry[
                        "result_sha256"
                    ]:
                        raise PublicationError(f"{run_id}: result hash linkage mismatch")
                    if entries["raw-trace.jsonl"]["sha256"] != source_entry[
                        "raw_trace_sha256"
                    ]:
                        raise PublicationError(f"{run_id}: raw trace hash linkage mismatch")

                    declared_run_bytes = len(publish_bytes) + sum(
                        entry["size_bytes"] for entry in entries.values()
                    )
                    if global_bytes + declared_run_bytes > MAX_PUBLICATION_BYTES:
                        raise PublicationError(
                            "publication exceeds global hard size limit"
                        )

                    relative_run_dir = f"runs/{index:02d}-{run_id}"
                    _write_deterministic_gzip_bytes(
                        staging_root,
                        f"{relative_run_dir}/{PUBLISH_MANIFEST_PATH}",
                        publish_bytes,
                    )
                    _remember_staged_artifact(
                        staged_expectations,
                        staging_root,
                        f"{relative_run_dir}/{PUBLISH_MANIFEST_PATH}",
                        compressed=True,
                        size_bytes=len(publish_bytes),
                        sha256=hashlib.sha256(publish_bytes).hexdigest(),
                    )
                    global_bytes += len(publish_bytes)
                    for relative in sorted(entries):
                        size, digest = _copy_checked_artifact(
                            source_root,
                            relative,
                            entries[relative],
                            staging_root,
                            f"{relative_run_dir}/{relative}",
                        )
                        global_bytes += size
                        _remember_staged_artifact(
                            staged_expectations,
                            staging_root,
                            f"{relative_run_dir}/{relative}",
                            compressed=True,
                            size_bytes=size,
                            sha256=digest,
                        )
                    published_entry["run_dir"] = relative_run_dir

            encoded_manifest = _encode_behavior_manifest(published_manifest)
            with _open_destination_exclusive(
                staging_fd, "behavior-run-manifest.json"
            ) as manifest_destination:
                manifest_destination.write(encoded_manifest)
                manifest_destination.flush()
                os.fsync(manifest_destination.fileno())
            manifest_size, manifest_hash = artifact_measure(
                staging_root,
                "behavior-run-manifest.json",
                max_bytes=MAX_BEHAVIOR_MANIFEST_BYTES,
                expected_size=len(encoded_manifest),
            )
            if manifest_size != len(encoded_manifest) or manifest_hash != hashlib.sha256(
                encoded_manifest
            ).hexdigest():
                raise PublicationError("staged behavior manifest verification failed")
            _remember_staged_artifact(
                staged_expectations,
                staging_root,
                "behavior-run-manifest.json",
                compressed=False,
                size_bytes=manifest_size,
                sha256=manifest_hash,
            )
            observed_output_files = _inventory_files(staging_fd)
            if observed_output_files != set(staged_expectations):
                raise PublicationError("publication output contains an unexpected file")
            _verify_staged_artifacts(staging_root, staged_expectations)
            os.fsync(staging_fd)
            os.close(staging_fd)
            staging_fd = -1
            _rename_noreplace(parent_fd, staging_name, output_name)
            os.fsync(parent_fd)
            published = True
            return {
                "manifest": str(absolute_parent / output_name / "behavior-run-manifest.json"),
                "runs": len(published_manifest["runs"]),
                "files": len(observed_output_files),
                "uncompressed_bytes": global_bytes,
                "manifest_sha256": hashlib.sha256(encoded_manifest).hexdigest(),
            }
        finally:
            if staging_fd >= 0:
                os.close(staging_fd)
            if not published:
                _remove_tree_at(parent_fd, staging_name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path)
    destination.add_argument("--bind-output", type=Path)
    args = parser.parse_args()
    grading_identity: dict[str, Any] | None = None
    operation = "bound" if args.bind_output is not None else "published"
    try:
        grading_identity = _verified_grading_identity()
        if args.bind_output is not None:
            report = bind_behavior_manifest_file(
                args.manifest,
                args.bind_output,
                grading_identity=grading_identity,
            )
            grading_identity = report.pop("grading_harness_identity")
        else:
            report = publish_behavior_manifest(
                args.manifest,
                args.output,
                grading_identity=grading_identity,
            )
    except Exception as exc:
        print(
            json.dumps(
                {
                    operation: False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "grading_harness_identity": grading_identity,
                },
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                operation: True,
                **report,
                "grading_harness_identity": grading_identity,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
