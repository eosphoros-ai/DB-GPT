"""Revisioned, instance-scoped suite drafts and immutable generated packages."""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterator, Optional

from .loader import (
    PLUGIN_MANIFEST_FILENAME,
    load_suite_dir,
    package_digest,
    read_skill_metadata,
    resolve_suites_dir,
)

# These identifiers have concrete factories in both harnesses. Do not use
# conceptual tool labels from suite templates as runtime dependencies.
CREATION_CAPABILITIES = {
    "sql_query",
    "code",
    "bash",
    "html_interpreter",
    "web_search",
    "web_fetch",
    "export_csv",
    "chart_query",
    "generate_report",
    "semantic_get_metadata",
    "semantic_search_business",
    "semantic_search_metrics",
    "semantic_get_metric",
}
MAX_BYTES = 50 * 1024 * 1024
MAX_FILES = 256
_LOCK = threading.RLock()


def safe_path(root: Path, relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or "\x00" in relative
        or PurePosixPath(relative).is_absolute()
        or any(part in ("", ".", "..") for part in relative.split("/"))
    ):
        raise ValueError(f"unsafe package path: {relative}")
    target = root / relative
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"package path escapes root: {relative}")
    if any(
        p.is_symlink()
        for p in [target, *target.parents]
        if p == root or p.is_relative_to(root)
    ):
        raise ValueError(f"symlink in package path: {relative}")
    return target


class SuiteCreationStore:
    """Atomic filesystem metadata; drafts are never scanned as runtime suites."""

    def __init__(self, root: Optional[Path] = None):
        self.root = (
            root
            or Path(
                os.environ.get("DBGPT_SUITE_CREATION_DIR", ".runtime/suite-creation")
            ).resolve()
        )
        self.root.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def locked(self) -> Iterator[None]:
        import fcntl

        with _LOCK, (self.root / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _dir(self, kind: str, identity: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise ValueError("invalid draft/artifact id")
        return self.root / kind / identity

    @staticmethod
    def _save(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}-{uuid.uuid4().hex}")
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)

    def _load(self, kind: str, identity: str) -> Dict[str, Any]:
        path = self._dir(kind, identity) / "metadata.json"
        if not path.is_file():
            raise ValueError(f"{kind} not found")
        return json.loads(path.read_text("utf-8"))

    def create(self, requirement: str, conv_id: str = "") -> Dict[str, Any]:
        with self.locked():
            draft = {
                "draft_id": uuid.uuid4().hex,
                "revision": 0,
                "requirement": requirement[:20000],
                "conv_id": conv_id,
                "scope": "instance",
                "files": {},
            }
            self._save(self._dir("drafts", draft["draft_id"]) / "metadata.json", draft)
            return draft

    def read(self, draft_id: str) -> Dict[str, Any]:
        return self._load("drafts", draft_id)

    def write(
        self, draft_id: str, files: Dict[str, str], expected_revision: int
    ) -> Dict[str, Any]:
        with self.locked():
            draft = self.read(draft_id)
            if draft["revision"] != expected_revision:
                raise ValueError("revision conflict: reload draft before editing")
            merged = {**draft["files"], **files}
            if len(merged) > MAX_FILES:
                raise ValueError("package exceeds 256 files")
            size = 0
            for name, text in merged.items():
                safe_path(self._dir("drafts", draft_id), name)
                if not isinstance(text, str) or Path(name).suffix not in (
                    ".md",
                    ".json",
                ):
                    raise ValueError("generated suites accept Markdown and JSON files")
                size += len(text.encode("utf-8"))
            if size > MAX_BYTES:
                raise ValueError("package exceeds 50MB")
            draft.update(files=merged, revision=expected_revision + 1)
            self._save(self._dir("drafts", draft_id) / "metadata.json", draft)
            return draft

    @staticmethod
    def _materialize(root: Path, files: Dict[str, str]) -> None:
        for name, text in files.items():
            path = safe_path(root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, "utf-8")

    def validate_files(self, files: Dict[str, str]) -> Dict[str, Any]:
        errors, warnings = [], []
        dependencies, pending = [], []
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            root = Path(temp)
            try:
                if len(files) > MAX_FILES:
                    raise ValueError("too many files")
                if (
                    sum(len(value.encode("utf-8")) for value in files.values())
                    > MAX_BYTES
                ):
                    raise ValueError("package exceeds 50MB")
                self._materialize(root, files)
                raw = json.loads(files.get(PLUGIN_MANIFEST_FILENAME, "{}"))
                if not isinstance(raw, dict):
                    raise ValueError("plugin.json must contain an object")
                for key in ("name", "version", "description"):
                    if not isinstance(raw.get(key), str) or not raw[key].strip():
                        errors.append(f"plugin.json requires {key}")
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", raw.get("name", "")):
                    errors.append(
                        "name must be a lowercase slug, at most 80 characters"
                    )
                if not re.fullmatch(
                    r"\d+\.\d+\.\d+(?:[-+][\w.-]+)?", raw.get("version", "")
                ):
                    errors.append("version must be semver (e.g. 1.0.0)")
                extension = raw.get("dbgpt") or {}
                if not isinstance(extension, dict):
                    raise ValueError("dbgpt must be an object")
                for field in ("tools", "context_defaults", "output_contract"):
                    if field in extension and not isinstance(extension[field], dict):
                        raise ValueError(f"dbgpt.{field} must be an object")
                for field in ("commands", "artifacts", "recommended_questions"):
                    if field in extension and not isinstance(extension[field], list):
                        raise ValueError(f"dbgpt.{field} must be a list")
                if extension.get("execution", "react") != "react":
                    errors.append("generated suites currently support react execution")
                sop = extension.get("sop")
                if (
                    not isinstance(sop, str)
                    or sop not in files
                    or not files.get(sop, "").strip()
                ):
                    errors.append("dbgpt.sop must reference a nonempty workflow file")
                else:
                    safe_path(root, sop)
                if not files.get("README.md", "").strip():
                    errors.append("README.md is required")
                skill_paths = raw.get("skills")
                if not isinstance(skill_paths, list) or not skill_paths:
                    errors.append("at least one skill is required")
                    skill_paths = []
                skill_names = set()
                for rel in skill_paths:
                    skill_path = safe_path(root, rel)
                    if skill_path.is_dir():
                        skill_path = skill_path / "SKILL.md"
                    metadata = read_skill_metadata(skill_path)
                    name = metadata["name"]
                    if name in skill_names:
                        errors.append(f"duplicate skill: {name}")
                    skill_names.add(name)
                    if not metadata.get("description"):
                        errors.append(f"skill description missing: {name}")
                    body = re.sub(
                        r"\A---\r?\n.*?\r?\n---",
                        "",
                        skill_path.read_text("utf-8"),
                        count=1,
                        flags=re.S,
                    ).strip()
                    if len(body) < 40:
                        errors.append(f"skill body incomplete: {name}")
                for command in extension.get("commands", []):
                    if not isinstance(command, dict):
                        raise ValueError("commands must contain objects")
                    if command.get("skill") not in skill_names:
                        errors.append(
                            f"command targets missing skill: {command.get('name')}"
                        )
                tools = extension.get("tools") or {}
                dependencies = tools.get("allow", [])
                if not isinstance(dependencies, list) or not all(
                    isinstance(x, str) for x in dependencies
                ):
                    raise ValueError(
                        "dbgpt.tools.allow must be a list of tool identifiers"
                    )
                for name in dependencies:
                    if name not in CREATION_CAPABILITIES:
                        errors.append(f"required platform tool unavailable: {name}")
                database_tools = {
                    "sql_query",
                    "chart_query",
                    "semantic_get_metadata",
                    "semantic_search_business",
                    "semantic_search_metrics",
                    "semantic_get_metric",
                }
                if database_tools.intersection(dependencies) and (
                    extension.get("context_defaults", {}).get("datasource")
                    != "required"
                    or "database" not in extension.get("required_resources", [])
                ):
                    errors.append(
                        "sql_query requires context_defaults.datasource=required"
                    )
                if (
                    extension.get("context_defaults", {}).get("datasource")
                    == "required"
                ):
                    pending.append("database")
                resources = extension.get("required_resources", [])
                if not isinstance(resources, list) or any(
                    x != "database" for x in resources
                ):
                    errors.append(
                        "P0 supports database configuration; "
                        "other required resources need an extension"
                    )
                else:
                    pending.extend(resources)
                contract = extension.get("output_contract")
                if not isinstance(contract, dict) or not contract.get("completion"):
                    errors.append("output_contract.completion is required")
                if not extension.get("artifacts"):
                    errors.append("dbgpt.artifacts must declare outputs")
                for output in extension.get("artifacts", []):
                    if not isinstance(output, dict) or output.get("type") not in (
                        "markdown",
                        "html",
                        "file",
                        "query",
                        "image",
                        "code",
                        "csv",
                        "table",
                        "chart",
                    ):
                        errors.append("unsupported artifact output declaration")
                for name, text in files.items():
                    if not name.endswith(".md"):
                        continue
                    for link in re.findall(
                        r"\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", text
                    ):
                        if link.startswith(("https://", "http://", "#", "mailto:")):
                            continue
                        candidate = (
                            root / PurePosixPath(name).parent / link.split("#")[0]
                        )
                        if not candidate.resolve().is_relative_to(root.resolve()):
                            raise ValueError(f"reference escapes package: {link}")
                        referenced = safe_path(
                            root,
                            candidate.resolve().relative_to(root.resolve()).as_posix(),
                        )
                        if not referenced.is_file():
                            errors.append(f"missing reference: {name} -> {link}")
                pkg = load_suite_dir(root)
                if pkg is None:
                    errors.append("package loader rejected generated suite")
                elif pkg.warnings:
                    errors.extend(pkg.warnings)
            except (ValueError, TypeError, KeyError, OSError) as exc:
                errors.append(str(exc))
        warnings.append("尚未执行真实任务试跑")
        return {
            "status": "invalid" if errors else "ready",
            "errors": errors,
            "warnings": warnings,
            "dependencies": dependencies,
            "pending_configuration": sorted(set(pending)),
            "trial_status": "not_run",
        }

    def validate(self, draft_id: str, expected_revision: int) -> Dict[str, Any]:
        with self.locked():
            draft = self.read(draft_id)
            if draft["revision"] != expected_revision:
                raise ValueError("revision conflict")
            return {
                **self.validate_files(draft["files"]),
                "revision": expected_revision,
            }

    def build(
        self,
        draft_id: str,
        expected_revision: int,
        source_artifact_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.locked():
            if source_artifact_id:
                self.artifact(source_artifact_id)
            draft = self.read(draft_id)
            if draft["revision"] != expected_revision:
                raise ValueError("revision conflict")
            report = self.validate_files(draft["files"])
            if report["errors"]:
                raise ValueError("validation failed: " + "; ".join(report["errors"]))
            identity = uuid.uuid4().hex
            destination = self._dir("artifacts", identity)
            destination.mkdir(parents=True)
            package = destination / "package"
            package.mkdir()
            self._materialize(package, draft["files"])
            raw = json.loads(draft["files"][PLUGIN_MANIFEST_FILENAME])
            archive = destination / "package.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(package.rglob("*")):
                    if path.is_file():
                        zf.write(
                            path,
                            f"{raw['name']}/{path.relative_to(package).as_posix()}",
                        )
            artifact = {
                "artifact_type": "expert_suite",
                "artifact_id": identity,
                "draft_id": draft_id,
                "revision": expected_revision,
                "suite_name": raw["name"],
                "display": raw.get("displayNameCn")
                or raw.get("displayName")
                or raw["name"],
                "description": raw["description"],
                "version": raw["version"],
                "package_digest": package_digest(package),
                "validation": report,
                "files": draft["files"],
                "size": archive.stat().st_size,
                "scope": "instance",
            }
            self._save(destination / "metadata.json", artifact)
            if source_artifact_id:
                path = self._dir("artifacts", source_artifact_id) / "revisions.json"
                revisions = (
                    json.loads(path.read_text("utf-8"))
                    if path.exists()
                    else {"ids": []}
                )
                revisions["ids"].append(identity)
                self._save(path, revisions)
            return artifact

    def artifact(self, artifact_id: str) -> Dict[str, Any]:
        return self._load("artifacts", artifact_id)

    def revisions(self, artifact_id: str) -> list:
        self.artifact(artifact_id)
        path = self._dir("artifacts", artifact_id) / "revisions.json"
        return json.loads(path.read_text("utf-8"))["ids"] if path.exists() else []

    def configuration(self, name: str) -> Dict[str, Any]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", name):
            return {}
        path = self.root / "configuration" / f"{name}.json"
        return json.loads(path.read_text("utf-8")) if path.exists() else {}

    def has_installation_intent(self, name: str) -> bool:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", name):
            return False
        return (self.root / "installations" / f"{name}.json").is_file()

    def configure(self, artifact_id: str, database_name: str, service: Any) -> Any:
        from dbgpt_serve.datasource.manages import ConnectorManager

        with self.locked():
            suite = self.installation(artifact_id, service)
            if not suite:
                raise ValueError("install suite before configuring")
            if not database_name:
                raise ValueError("select a database")
            manager = ConnectorManager.get_instance(service._system_app)
            manager.get_connector(database_name)
            self._save(
                self.root / "configuration" / f"{suite.name}.json",
                {"database_name": database_name},
            )
            return service.enable(suite.name)

    def download(self, artifact_id: str) -> Path:
        self.artifact(artifact_id)
        return self._dir("artifacts", artifact_id) / "package.zip"

    def installation(self, artifact_id: str, service: Any) -> Optional[Any]:
        artifact = self.artifact(artifact_id)
        existing = service.get(artifact["suite_name"])
        if existing and existing.package_digest == artifact["package_digest"]:
            return existing
        return None

    def install(self, artifact_id: str, digest: str, service: Any) -> Any:
        with self.locked():
            artifact = self.artifact(artifact_id)
            package = self._dir("artifacts", artifact_id) / "package"
            if (
                artifact["package_digest"] != digest
                or package_digest(package) != digest
            ):
                raise ValueError("artifact digest mismatch")
            report = self.validate_files(artifact["files"])
            if report["errors"]:
                raise ValueError("installation blocked: " + "; ".join(report["errors"]))
            existing = service.get(artifact["suite_name"])
            if existing:
                if existing.package_digest == digest:
                    return existing
                raise ValueError(
                    "same-name conflict: change plugin.json name and rebuild"
                )
            root = resolve_suites_dir(service.config.suites_dir)
            if root is None:
                raise ValueError("suites directory not configured")
            target = safe_path(root, artifact["suite_name"])
            if target.exists() and package_digest(target) != digest:
                raise ValueError("same-name package exists on disk: rename and rebuild")
            from .installer import commit_package

            # Startup scanning must not activate an orphaned generated package
            # if the process exits between file publication and DB commit.
            intent = self.root / "installations" / f"{artifact['suite_name']}.json"
            self._save(
                intent,
                {
                    "artifact_id": artifact_id,
                    "digest": digest,
                    "status": "installing",
                },
            )

            def register(installed: Path):
                current = service.get(artifact["suite_name"])
                if current:
                    if current.package_digest == digest:
                        return current
                    raise ValueError("same-name registry conflict: rename and rebuild")
                pkg = load_suite_dir(installed)
                if pkg is None or pkg.digest != digest:
                    raise ValueError("installed package digest mismatch")
                return service.install_generated_package(
                    pkg, artifact_id, bool(report["pending_configuration"])
                )

            installed = commit_package(
                root,
                package,
                artifact["suite_name"],
                register,
                replace_existing=False,
            )
            self._save(
                intent,
                {
                    "artifact_id": artifact_id,
                    "digest": digest,
                    "status": "installed",
                },
            )
            return installed
