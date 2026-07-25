from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any


MANIFEST_FILENAME = "kit.toml"
SUPPORTED_SCHEMA_VERSION = 1
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
_PYTHON_VERSION_RE = re.compile(r"^(?P<major>[0-9]+)\.(?P<minor>[0-9]+)$")
_SKILL_NAME_RE = re.compile(r"(?m)^name:\s*['\"]?(?P<name>[A-Za-z0-9._-]+)['\"]?\s*$")
_DESCRIPTION_RE = re.compile(r"(?m)^description:\s*(?P<value>.*)$")
_RESOURCE_RE = re.compile(r"`(?P<path>(?:references|agents|scripts)/[^`\s]+)")


class ManifestError(ValueError):
    """Raised when kit.toml cannot be parsed into the supported schema."""


@dataclass(frozen=True)
class InstallSpec:
    kit_link: str
    agents_link: str
    skills_dir: str
    retired_skills: tuple[str, ...]


@dataclass(frozen=True)
class SkillSpec:
    name: str
    path: str
    entrypoint: str

    def root(self, repo_root: Path) -> Path:
        return repo_root / self.path

    def entrypoint_path(self, repo_root: Path) -> Path:
        return self.root(repo_root) / self.entrypoint


@dataclass(frozen=True)
class KitManifest:
    schema_version: int
    kit_version: str
    minimum_python: tuple[int, int]
    minimum_python_text: str
    normative_source: str
    install: InstallSpec
    skills: tuple[SkillSpec, ...]
    path: Path


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{field} must be a TOML table")
    return value


def _require_string(mapping: dict[str, Any], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field} must be a non-empty string")
    return value.strip()


def _safe_relative_path(value: str, field: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ManifestError(f"{field} must be a safe repository-relative path: {value!r}")
    return path.as_posix()


def _skill_name_list(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ManifestError(f"{field} must be an array of skill names")

    names: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", item):
            raise ManifestError(f"{field}[{index}] is not a valid skill name: {item!r}")
        names.append(item)
    if len(names) != len(set(names)):
        raise ManifestError(f"{field} contains duplicate skill names")
    return tuple(names)


def load_manifest(repo_root: Path) -> KitManifest:
    repo_root = repo_root.resolve()
    manifest_path = repo_root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ManifestError(f"missing {MANIFEST_FILENAME} at {manifest_path}")

    try:
        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ManifestError(f"cannot read {manifest_path}: {exc}") from exc

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int):
        raise ManifestError("schema_version must be an integer")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported schema_version {schema_version}; "
            f"expected {SUPPORTED_SCHEMA_VERSION}"
        )

    kit_version = _require_string(data, "kit_version")
    if not _VERSION_RE.fullmatch(kit_version):
        raise ManifestError(f"kit_version is not a semantic version: {kit_version!r}")

    minimum_python_text = _require_string(data, "minimum_python")
    python_match = _PYTHON_VERSION_RE.fullmatch(minimum_python_text)
    if python_match is None:
        raise ManifestError(
            f"minimum_python must use major.minor form: {minimum_python_text!r}"
        )
    minimum_python = (
        int(python_match.group("major")),
        int(python_match.group("minor")),
    )

    normative_source = _safe_relative_path(
        _require_string(data, "normative_source"), "normative_source"
    )

    install_data = _require_mapping(data.get("install"), "install")
    install = InstallSpec(
        kit_link=_safe_relative_path(
            _require_string(install_data, "kit_link"), "install.kit_link"
        ),
        agents_link=_safe_relative_path(
            _require_string(install_data, "agents_link"), "install.agents_link"
        ),
        skills_dir=_safe_relative_path(
            _require_string(install_data, "skills_dir"), "install.skills_dir"
        ),
        retired_skills=_skill_name_list(
            install_data.get("retired_skills"), "install.retired_skills"
        ),
    )

    raw_skills = data.get("skills")
    if not isinstance(raw_skills, list) or not raw_skills:
        raise ManifestError("skills must contain at least one [[skills]] table")

    skills: list[SkillSpec] = []
    for index, raw_skill in enumerate(raw_skills):
        skill_data = _require_mapping(raw_skill, f"skills[{index}]")
        name = _require_string(skill_data, "name")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            raise ManifestError(f"skills[{index}].name is invalid: {name!r}")
        path = _safe_relative_path(
            _require_string(skill_data, "path"), f"skills[{index}].path"
        )
        entrypoint = _safe_relative_path(
            _require_string(skill_data, "entrypoint"),
            f"skills[{index}].entrypoint",
        )
        skills.append(SkillSpec(name=name, path=path, entrypoint=entrypoint))

    return KitManifest(
        schema_version=schema_version,
        kit_version=kit_version,
        minimum_python=minimum_python,
        minimum_python_text=minimum_python_text,
        normative_source=normative_source,
        install=install,
        skills=tuple(skills),
        path=manifest_path,
    )


def read_skill_metadata(skill_file: Path) -> tuple[str | None, str | None]:
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return None, None

    if not text.startswith("---\n"):
        return None, None
    closing = text.find("\n---\n", 4)
    if closing == -1:
        return None, None
    frontmatter = text[4:closing]

    name_match = _SKILL_NAME_RE.search(frontmatter)
    declared_name = name_match.group("name") if name_match else None

    description_match = _DESCRIPTION_RE.search(frontmatter)
    if description_match is None:
        return declared_name, None

    raw_description = description_match.group("value").strip()
    if raw_description in {"|", ">", "|-", ">-", "|+", ">+"}:
        block_lines: list[str] = []
        remainder = frontmatter[description_match.end() :].splitlines()
        for line in remainder:
            if not line.strip():
                if block_lines:
                    block_lines.append("")
                continue
            if not line.startswith((" ", "\t")):
                break
            block_lines.append(line.strip())
        description = " ".join(line for line in block_lines if line).strip()
    else:
        description = raw_description.strip("'\"").strip()

    return declared_name, description or None


def referenced_skill_resources(skill_file: Path) -> tuple[str, ...]:
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return ()

    resources: set[str] = set()
    for match in _RESOURCE_RE.finditer(text):
        value = match.group("path").rstrip(".,:;)]}")
        if "<" in value or ">" in value:
            continue
        resources.add(value)
    return tuple(sorted(resources))


def validate_manifest(manifest: KitManifest, repo_root: Path) -> list[str]:
    repo_root = repo_root.resolve()
    errors: list[str] = []

    normative_path = repo_root / manifest.normative_source
    if not normative_path.is_file():
        errors.append(f"normative source is missing: {manifest.normative_source}")

    names = [skill.name for skill in manifest.skills]
    paths = [skill.path for skill in manifest.skills]
    if len(names) != len(set(names)):
        errors.append("manifest contains duplicate skill names")
    if len(paths) != len(set(paths)):
        errors.append("manifest contains duplicate skill paths")

    retired_conflicts = sorted(set(names) & set(manifest.install.retired_skills))
    if retired_conflicts:
        errors.append(
            "active skills also listed as retired: " + ", ".join(retired_conflicts)
        )

    install_paths = (
        ("install.kit_link", Path(manifest.install.kit_link)),
        ("install.agents_link", Path(manifest.install.agents_link)),
        ("install.skills_dir", Path(manifest.install.skills_dir)),
    )
    for index, (left_name, left_path) in enumerate(install_paths):
        if len(left_path.parts) != 1:
            errors.append(
                f"{left_name} must be a single path component: "
                f"{left_path.as_posix()!r}"
            )
        for right_name, right_path in install_paths[index + 1 :]:
            if (
                left_path == right_path
                or left_path in right_path.parents
                or right_path in left_path.parents
            ):
                errors.append(
                    "managed install paths overlap: "
                    f"{left_name}={left_path.as_posix()!r}, "
                    f"{right_name}={right_path.as_posix()!r}"
                )

    manifest_skill_paths: set[str] = set()
    for skill in manifest.skills:
        manifest_skill_paths.add(Path(skill.path).as_posix())
        skill_root = skill.root(repo_root)
        entrypoint = skill.entrypoint_path(repo_root)
        if not skill_root.is_dir():
            errors.append(f"skill directory is missing: {skill.path}")
            continue
        if Path(skill.path).name != skill.name:
            errors.append(
                f"skill path/name mismatch: {skill.path!r} does not end in {skill.name!r}"
            )
        if not entrypoint.is_file():
            errors.append(f"skill entrypoint is missing: {entrypoint.relative_to(repo_root)}")
            continue

        declared_name, description = read_skill_metadata(entrypoint)
        if declared_name != skill.name:
            errors.append(
                f"skill frontmatter mismatch in {entrypoint.relative_to(repo_root)}: "
                f"expected {skill.name!r}, found {declared_name!r}"
            )
        if description is None:
            errors.append(
                f"skill description is missing or empty in "
                f"{entrypoint.relative_to(repo_root)}"
            )

        contract_documents = [entrypoint]
        contract_documents.extend(
            path for path in skill_root.rglob("*.md") if path != entrypoint
        )
        for document in contract_documents:
            for resource in referenced_skill_resources(document):
                resource_parts = Path(resource).parts
                if ".." in resource_parts:
                    errors.append(
                        f"unsafe resource referenced by {document.relative_to(repo_root)}: "
                        f"{resource}"
                    )
                    continue
                resource_path = skill_root / resource
                if not resource_path.exists():
                    errors.append(
                        f"missing resource referenced by {document.relative_to(repo_root)}: "
                        f"{resource}"
                    )

    skills_root = repo_root / "skills"
    discovered = {
        path.parent.relative_to(repo_root).as_posix()
        for path in skills_root.glob("*/SKILL.md")
    }
    unlisted = sorted(discovered - manifest_skill_paths)
    missing = sorted(manifest_skill_paths - discovered)
    if unlisted:
        errors.append(f"skills missing from manifest: {', '.join(unlisted)}")
    if missing:
        errors.append(f"manifest skills without SKILL.md: {', '.join(missing)}")

    return errors
