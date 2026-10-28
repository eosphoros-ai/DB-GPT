"""Scenario-suite and native QwenWork plugin package loader.

A package contains ``.qwenwork-plugin/plugin.json`` and skill frontmatter,
or a legacy ``suite.yaml`` with optional prompts, skills and few shots.
The package on disk is the **source of truth**; this loader only reads it and
projects a renderable snapshot for the registry.

Parsing is fail-soft (design: scenario-suite-impl-plan §一): required fields
must exist, other fields get a coarse type check, bad fields are skipped with
a warning instead of aborting the whole scan.  No jsonschema dependency.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "suite.yaml"
PLUGIN_MANIFEST_FILENAME = ".qwenwork-plugin/plugin.json"
VALID_KINDS = ("scenario-suite", "scenario-plugin")
REQUIRED_FIELDS = ("kind", "name", "version")

# Fields projected into manifest_snapshot (home tabs / routing / bind).
# Deliberately excludes ``sop`` body text: the playbook is read from the
# package at bind time, never duplicated into the DB.
SNAPSHOT_FIELDS = (
    "display",
    "display_en",
    "icon",
    "scenario_id",
    "execution",
    "routing",
    "recommended_questions",
    "commands",
    "tools",
    "approval_overrides",
    "artifacts",
    "context_defaults",
    "semantic",
    "output_contract",
    "description",
    "description_en",
    "skill_details",
    "author",
    "tags",
    "package_format",
    "required_resources",
)

_TYPE_CHECKS: Dict[str, type] = {
    "name": str,
    "version": str,
    "display": str,
    "display_en": str,
    "icon": str,
    "scenario_id": str,
    "execution": str,
    "description": str,
    "description_en": str,
    "author": str,
    "sop": str,
    "routing": dict,
    "tools": dict,
    "context_defaults": dict,
    "semantic": dict,
    "approval_overrides": list,
    "recommended_questions": list,
    "commands": list,
    "artifacts": list,
    "skills": list,
    "tags": list,
}


@dataclass
class SuitePackage:
    """A parsed suite package (in-memory only)."""

    name: str
    version: str
    path: str
    digest: str
    manifest: Dict[str, Any]
    snapshot: Dict[str, Any]
    skills: List[str]
    warnings: List[str] = field(default_factory=list)


def resolve_suites_dir(configured: Optional[str] = None) -> Optional[Path]:
    """Resolve the suites root directory, fail-soft to None."""
    candidates: List[Path] = []
    if configured:
        candidates.append(Path(configured))
    env = os.environ.get("DBGPT_SUITES_DIR")
    if env:
        candidates.append(Path(env))
    candidates.append(Path.cwd() / "assets" / "suites")
    # Repo-root fallback when the server runs from a sub-directory.
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "assets" / "suites")
    for cand in candidates:
        if cand.is_dir():
            return cand
    return None


def package_digest(path: Path) -> str:
    """sha256 over (relative path, content) pairs, sorted for stability."""
    h = hashlib.sha256()
    for f in sorted(p for p in Path(path).rglob("*") if p.is_file()):
        rel = f.relative_to(path).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _load_yaml(path: Path) -> Dict[str, Any]:
    import yaml  # lazy import; PyYAML is a runtime dependency of dbgpt-core

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _collect_skills(
    path: Path, manifest: Dict[str, Any], warnings: List[str]
) -> List[str]:
    """Resolve the skill list declared in the manifest, fallback to dir scan."""
    skills: List[str] = []
    for item in manifest.get("skills") or []:
        if isinstance(item, dict):
            sname = item.get("name")
            rel = item.get("path")
        elif isinstance(item, str):
            sname = Path(item).name
            rel = item
        else:
            warnings.append(f"skills entry ignored (bad type): {item!r}")
            continue
        if not sname:
            warnings.append(f"skills entry ignored (no name): {item!r}")
            continue
        skill_md = Path(path) / (rel or f"skills/{sname}/SKILL.md")
        if not skill_md.is_file():
            warnings.append(f"skill SKILL.md missing: {skill_md}")
        skills.append(str(sname))
    if not skills:
        skills_dir = Path(path) / "skills"
        if skills_dir.is_dir():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir() and (d / "SKILL.md").is_file():
                    skills.append(d.name)
    return skills


def _frontmatter_desc(path: Path) -> str:
    """Read description_zh (fallback description) from a SKILL.md frontmatter."""
    import re

    try:
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 - unreadable skill file yields empty summary
        return ""
    fm_match = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not fm_match:
        return ""
    frontmatter = fm_match.group(1)
    for key in ("description_zh", "description"):
        kv = re.search(rf"^{key}:\s*(.+)$", frontmatter, re.M)
        if kv:
            return kv.group(1).strip().strip('"')
    return ""


def read_skill_metadata(path: Path) -> Dict[str, Any]:
    """Read the standard YAML frontmatter without interpreting the skill body."""
    import yaml

    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not match:
        raise ValueError(f"skill frontmatter missing: {path.name}")
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        # Generated plugins use flat frontmatter and sometimes leave colons
        # in descriptions unquoted. Preserve those strings without rewriting
        # the user's package; booleans still govern menu visibility.
        metadata = {}
        for line in match.group(1).splitlines():
            entry = re.match(r"^([\w-]+):\s*(.*)$", line)
            if not entry:
                raise ValueError(f"unsupported skill frontmatter: {path.name}")
            key, value = entry.groups()
            metadata[key] = (
                value.lower() == "true"
                if value.lower() in ("true", "false")
                else value.strip().strip("\"'")
            )
    if not isinstance(metadata, dict) or not isinstance(metadata.get("name"), str):
        raise ValueError(f"skill frontmatter must declare a name: {path.name}")
    return metadata


def _load_plugin_manifest(dirpath: Path) -> Dict[str, Any]:
    """Project QwenWork's native plugin format into the runtime suite index.

    The JSON manifest and SKILL.md files stay authoritative and unmodified.
    This projection is in memory only; no suite.yaml is generated.
    """
    root = dirpath.resolve()
    raw = json.loads((root / PLUGIN_MANIFEST_FILENAME).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("plugin.json must contain an object")
    for key in ("name", "version"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(f"plugin.json must declare {key}")
    paths = raw.get("skills")
    if not isinstance(paths, list) or not paths:
        raise ValueError("plugin.json must declare skill directories")
    skills: List[Dict[str, Any]] = []
    commands: List[Dict[str, Any]] = []
    names = set()
    command_names = set()
    for rel in paths:
        if not isinstance(rel, str):
            raise ValueError("plugin skill paths must be strings")
        skill_file = (root / rel).resolve()
        if skill_file.is_dir():
            skill_file = (skill_file / "SKILL.md").resolve()
        if not skill_file.is_relative_to(root) or not skill_file.is_file():
            raise ValueError(f"invalid plugin skill path: {rel}")
        metadata = read_skill_metadata(skill_file)
        for key in (
            "name_en",
            "description_en",
            "argument-hint",
            "argument-hint-en",
            "argument-hint-zh",
        ):
            if key in metadata and not isinstance(metadata[key], str):
                raise ValueError(f"skill {key} must be a string")
        name = metadata["name"]
        if name in names:
            raise ValueError(f"duplicate plugin skill name: {name}")
        names.add(name)
        display = metadata.get("name_zh") or name
        description = metadata.get("description_zh") or metadata.get("description", "")
        if not isinstance(display, str) or not isinstance(description, str):
            raise ValueError(f"invalid plugin skill display or description: {name}")
        if not isinstance(metadata.get("user-invocable", True), bool):
            raise ValueError(f"user-invocable must be a boolean: {name}")
        invocable = metadata.get("user-invocable", True) is not False
        skills.append(
            {
                "name": name,
                "path": skill_file.relative_to(root).as_posix(),
                "display": display,
                "display_en": metadata.get("name_en") or name,
                "description": description,
                "description_en": metadata.get("description_en")
                or metadata.get("description", ""),
                "user_invocable": invocable,
            }
        )
        if invocable:
            command_name = metadata.get("command") or f"/{display}"
            if not isinstance(command_name, str) or not command_name.startswith("/"):
                raise ValueError(f"skill command must start with /: {name}")
            aliases = [f"/{name}", f"/{display}"]
            if metadata.get("name_en"):
                aliases.append(f"/{metadata['name_en']}")
            identifiers = set([command_name, *aliases])
            if identifiers & command_names:
                raise ValueError(f"duplicate plugin command or alias: {name}")
            command_names.update(identifiers)
            commands.append(
                {
                    "name": command_name,
                    "aliases": [
                        alias
                        for alias in dict.fromkeys(aliases)
                        if alias != command_name
                    ],
                    "skill": name,
                    "description": description,
                    "description_en": metadata.get("description_en")
                    or metadata.get("description", ""),
                    "display_en": (
                        command_name
                        if metadata.get("command")
                        else f"/{metadata.get('name_en') or name}"
                    ),
                    "prefill": metadata.get("argument-hint-zh")
                    or metadata.get("argument-hint")
                    or "",
                    "prefill_en": metadata.get("argument-hint-en")
                    or metadata.get("argument-hint")
                    or "",
                }
            )
    author = raw.get("author")
    manifest = {
        "kind": "scenario-plugin",
        "package_format": "qwenwork-plugin",
        "name": raw["name"],
        "version": raw["version"],
        "display": raw.get("displayNameCn") or raw.get("displayName") or raw["name"],
        "display_en": raw.get("displayNameEn") or raw.get("displayName") or raw["name"],
        "description": raw.get("descriptionZh") or raw.get("description", ""),
        "description_en": raw.get("descriptionEn") or raw.get("description", ""),
        "author": author.get("name", "") if isinstance(author, dict) else author or "",
        "tags": raw.get("tags") or [],
        "scenario_id": "expert",
        "execution": "react",
        "context_defaults": {"datasource": "optional"},
        "commands": commands,
        "skills": skills,
    }
    # Native metadata remains authoritative. DB-GPT runtime settings live in
    # a namespaced extension, so packages need only one manifest.
    extension = raw.get("dbgpt", {})
    if not isinstance(extension, dict):
        raise ValueError("plugin.json dbgpt extension must contain an object")
    runtime_fields = {
        "icon",
        "scenario_id",
        "execution",
        "sop",
        "tools",
        "context_defaults",
        "required_resources",
        "semantic",
        "artifacts",
        "approval_overrides",
        "routing",
        "recommended_questions",
        "output_contract",
        "analysis_defaults",
        "templates",
        "report_formats",
        "report_sections",
        "few_shots",
        "runbooks",
        "ui",
        "safety",
        "requires",
        "pin",
        "evals",
        "changelog",
        "approval_policy_notes",
        "output_contract_detail",
    }
    manifest.update(
        {key: value for key, value in extension.items() if key in runtime_fields}
    )
    return manifest


def read_skill_summaries(
    package_path: Optional[str], skill_names: List[str]
) -> List[Dict[str, Any]]:
    """Name + one-line summary per skill, for the suite detail page."""
    if not package_path:
        return []
    pkg = load_suite_dir(Path(package_path))
    declared = {
        item["name"]: item
        for item in (pkg.manifest.get("skills", []) if pkg else [])
        if isinstance(item, dict) and "name" in item
    }
    summaries: List[Dict[str, Any]] = []
    for name in skill_names:
        item = declared.get(name, {})
        skill_md = Path(package_path) / item.get("path", f"skills/{name}/SKILL.md")
        summaries.append(
            {
                "name": name,
                "display": item.get("display", name),
                "display_en": item.get("display_en", name),
                "description": item.get("description") or _frontmatter_desc(skill_md),
                "description_en": item.get("description_en", ""),
                "user_invocable": item.get("user_invocable", True),
            }
        )
    return summaries


def load_suite_dir(dirpath: Path) -> Optional[SuitePackage]:
    """Parse one suite package directory; None when unusable."""
    dirpath = Path(dirpath)
    plugin_path = dirpath / PLUGIN_MANIFEST_FILENAME
    manifest_path = dirpath / MANIFEST_FILENAME
    if not plugin_path.is_file() and not manifest_path.is_file():
        return None
    warnings: List[str] = []
    try:
        raw = (
            _load_plugin_manifest(dirpath)
            if plugin_path.is_file()
            else _load_yaml(manifest_path)
        )
    except Exception as exc:  # noqa: BLE001 - fail-soft by design
        logger.warning("suite manifest unparsable, skipped: %s (%s)", dirpath, exc)
        return None

    manifest: Dict[str, Any] = {}
    for key, value in raw.items():
        expected = _TYPE_CHECKS.get(key)
        if expected is not None and not isinstance(value, expected):
            warnings.append(
                f"field '{key}' has bad type {type(value).__name__}, skipped"
            )
            continue
        manifest[key] = value

    for req in REQUIRED_FIELDS:
        if req not in manifest:
            logger.warning(
                "suite %s missing required field '%s', skipped", dirpath, req
            )
            return None
    if manifest.get("kind") not in VALID_KINDS:
        logger.warning(
            "suite %s has unsupported kind %r, skipped", dirpath, manifest.get("kind")
        )
        return None
    manifest.setdefault("execution", "react")

    skills = _collect_skills(dirpath, manifest, warnings)
    snapshot = {k: manifest[k] for k in SNAPSHOT_FIELDS if k in manifest}
    snapshot["skills"] = skills
    snapshot["skill_details"] = [
        {
            key: item[key]
            for key in (
                "name",
                "display",
                "display_en",
                "description",
                "description_en",
                "user_invocable",
            )
            if key in item
        }
        for item in manifest.get("skills", [])
        if isinstance(item, dict)
    ]
    return SuitePackage(
        name=manifest["name"],
        version=str(manifest["version"]),
        path=str(dirpath),
        digest=package_digest(dirpath),
        manifest=manifest,
        snapshot=snapshot,
        skills=skills,
        warnings=warnings,
    )


def scan_suites(root: Optional[Path]) -> Tuple[List[SuitePackage], List[str]]:
    """Scan all suite packages under root; never raises for a bad package."""
    if root is None or not Path(root).is_dir():
        return [], [f"suites dir not found: {root}"]
    packages: List[SuitePackage] = []
    warnings: List[str] = []
    for child in sorted(Path(root).iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        pkg = load_suite_dir(child)
        if pkg is None:
            if (child / MANIFEST_FILENAME).is_file() or (
                child / PLUGIN_MANIFEST_FILENAME
            ).is_file():
                warnings.append(f"suite skipped due to manifest errors: {child.name}")
            continue
        warnings.extend(pkg.warnings)
        packages.append(pkg)
    return packages, warnings
