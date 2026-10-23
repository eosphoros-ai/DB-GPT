"""Scenario-suite package loader.

A suite package is a directory (or extracted zip) containing ``suite.yaml``
(the manifest) plus optional ``prompts/``, ``skills/`` and ``few_shots/``.
The package on disk is the **source of truth**; this loader only reads it and
projects a renderable snapshot for the registry.

Parsing is fail-soft (design: scenario-suite-impl-plan §一): required fields
must exist, other fields get a coarse type check, bad fields are skipped with
a warning instead of aborting the whole scan.  No jsonschema dependency.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "suite.yaml"
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
    "author",
    "tags",
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


def read_skill_summaries(
    package_path: Optional[str], skill_names: List[str]
) -> List[Dict[str, str]]:
    """Name + one-line summary per skill, for the suite detail page."""
    if not package_path:
        return []
    summaries: List[Dict[str, str]] = []
    for name in skill_names:
        skill_md = Path(package_path) / "skills" / name / "SKILL.md"
        summaries.append({"name": name, "description": _frontmatter_desc(skill_md)})
    return summaries


def load_suite_dir(dirpath: Path) -> Optional[SuitePackage]:
    """Parse one suite package directory; None when unusable."""
    dirpath = Path(dirpath)
    manifest_path = dirpath / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    warnings: List[str] = []
    try:
        raw = _load_yaml(manifest_path)
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
        if not child.is_dir():
            continue
        pkg = load_suite_dir(child)
        if pkg is None:
            if (child / MANIFEST_FILENAME).is_file():
                warnings.append(f"suite skipped due to manifest errors: {child.name}")
            continue
        warnings.extend(pkg.warnings)
        packages.append(pkg)
    return packages, warnings
