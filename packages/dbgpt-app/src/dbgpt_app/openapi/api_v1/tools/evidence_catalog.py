"""Private, session-scoped catalog of captured results and metric coordinates."""

import hashlib
import json
import logging
import math
import sqlite3
from decimal import Decimal
from pathlib import Path

from pydantic import TypeAdapter

from dbgpt.configs.model_config import PILOT_PATH
from dbgpt.core.interface.report import Artifact, normalize_result_selector
from dbgpt.core.interface.report_capture import (
    InMemoryArtifactSink,
    normalize_artifact_result_selector,
    select_artifact_result,
    select_result_value,
)

logger = logging.getLogger(__name__)


def catalog_path() -> Path:
    return Path(PILOT_PATH) / "data" / "report-evidence-catalog.sqlite3"


class EvidenceCatalog:
    """Persist exact result locations without guessing their business meaning."""

    def __init__(self, path: Path, *, owner_id: str = "local"):
        self.path = Path(path)
        self.owner_id = owner_id
        if not isinstance(owner_id, str) or not owner_id:
            raise ValueError("EVIDENCE_OWNER_REQUIRED")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS artifacts (owner_id TEXT NOT NULL, "
                "session_id TEXT NOT NULL, "
                "artifact_id TEXT NOT NULL, payload TEXT NOT NULL, "
                "PRIMARY KEY(owner_id, session_id, artifact_id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS metrics (owner_id TEXT NOT NULL, "
                "session_id TEXT NOT NULL, "
                "metric_id TEXT NOT NULL, artifact_id TEXT NOT NULL, "
                "payload TEXT NOT NULL, PRIMARY KEY(owner_id, session_id, metric_id))"
            )

    def _connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def save_artifact(self, session_id, artifact):
        if not session_id or artifact.execution.conv_uid != session_id:
            raise ValueError("EVIDENCE_SESSION_MISMATCH")
        # The complete result already lives at artifact.result.uri. Persist only
        # its validated coordinates and content address, not a second result
        # snapshot that would inflate storage and report context.
        payload_value = json.loads(artifact.model_dump_json(warnings="none"))
        if isinstance(payload_value.get("result"), dict):
            payload_value["result"]["inline"] = None
        payload = json.dumps(payload_value, ensure_ascii=False, sort_keys=True)
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM artifacts WHERE owner_id=? "
                "AND session_id=? AND artifact_id=?",
                (self.owner_id, session_id, artifact.artifact_id),
            ).fetchone()
            if row and json.loads(row[0]) != json.loads(payload):
                raise ValueError("EVIDENCE_ARTIFACT_CONFLICT")
            db.execute(
                "INSERT OR IGNORE INTO artifacts VALUES (?, ?, ?, ?)",
                (self.owner_id, session_id, artifact.artifact_id, payload),
            )

    def list_artifacts(self, session_id):
        adapter = TypeAdapter(Artifact)
        with self._connect() as db:
            rows = db.execute(
                "SELECT payload FROM artifacts WHERE owner_id=? AND session_id=? "
                "ORDER BY rowid",
                (self.owner_id, session_id),
            ).fetchall()
        artifacts = [adapter.validate_json(row[0]) for row in rows]
        if any(a.execution.conv_uid != session_id for a in artifacts):
            raise ValueError("EVIDENCE_SESSION_MISMATCH")
        return artifacts

    def register(
        self,
        session_id,
        artifact,
        selector,
        *,
        label=None,
        grain=None,
        meaning_source=None,
        _artifact_persisted=False,
    ):
        """Register a scalar after validating the artifact and field path."""
        if not session_id or artifact.execution.conv_uid != session_id:
            raise ValueError("EVIDENCE_SESSION_MISMATCH")
        if artifact.status != "succeeded" or artifact.type not in {"sql", "python"}:
            raise ValueError("EVIDENCE_ARTIFACT_INVALID")
        if not isinstance(selector, dict) or not selector:
            raise ValueError("EVIDENCE_SELECTOR_REQUIRED")
        if selector.get("kind") == "sql":
            selector = normalize_artifact_result_selector(artifact, selector)
            value = select_artifact_result(artifact, selector)
        else:
            selector = normalize_result_selector(selector)
            preview = artifact.result.inline if artifact.result is not None else None
            try:
                value = select_result_value(preview, selector)
            except (ValueError, TypeError):
                # A bounded preview can omit a valid result; verify against the
                # captured content address only for this explicit selection.
                selector = normalize_artifact_result_selector(artifact, selector)
                value = select_artifact_result(artifact, selector)
        if (
            not isinstance(value, (int, float, Decimal))
            or isinstance(value, bool)
            or (isinstance(value, float) and not math.isfinite(value))
            or (isinstance(value, Decimal) and not value.is_finite())
        ):
            raise ValueError("EVIDENCE_METRIC_SCALAR_REQUIRED")
        coordinate = {"artifact_id": artifact.artifact_id, "selector": selector}
        metric_id = (
            "metric-"
            + hashlib.sha256(
                json.dumps(coordinate, sort_keys=True, ensure_ascii=False).encode(
                    "utf-8"
                )
            ).hexdigest()[:24]
        )
        payload = {
            "metric_id": metric_id,
            "artifact_id": artifact.artifact_id,
            "run_id": artifact.execution.run_id,
            "selector": selector,
            "label": label,
            "grain": grain,
            "meaning_source": "producer_field" if label else "unknown",
            "status": "selector_validated",
        }
        if not payload["run_id"]:
            raise ValueError("EVIDENCE_RUN_REQUIRED")
        if label is not None and (not isinstance(label, str) or not label.strip()):
            raise ValueError("EVIDENCE_MEANING_INVALID")
        if grain is not None and (not isinstance(grain, str) or not grain.strip()):
            raise ValueError("EVIDENCE_GRAIN_INVALID")
        payload["meaning_source"] = meaning_source or (
            "producer_field" if label else "unknown"
        )
        if not _artifact_persisted:
            self.save_artifact(session_id, artifact)
        with self._connect() as db:
            insert = (
                "INSERT OR IGNORE INTO metrics VALUES (?, ?, ?, ?, ?)"
                if _artifact_persisted
                else "INSERT INTO metrics VALUES (?, ?, ?, ?, ?) ON CONFLICT("
                "owner_id, session_id, metric_id) DO UPDATE SET "
                "payload=excluded.payload"
            )
            db.execute(
                insert,
                (
                    self.owner_id,
                    session_id,
                    metric_id,
                    artifact.artifact_id,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
        return payload

    def list_metrics(self, session_id):
        with self._connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM metrics WHERE owner_id=? AND session_id=? "
                    "ORDER BY rowid",
                    (self.owner_id, session_id),
                )
            ]

    def register_observed_scalars(self, session_id, artifact):
        """Index simple scalars; field names remain unverified semantics."""
        if artifact.status != "succeeded" or artifact.type not in {"sql", "python"}:
            return
        # The capture already holds a bounded preview in memory. Never reload
        # a large result file just to build a small directory.
        result = artifact.result.inline if artifact.result is not None else None
        if isinstance(result, str) and result.lstrip().startswith(("{", "[")):
            try:
                result = json.loads(result)
            except ValueError:
                pass
        coordinates = []
        if artifact.type == "sql" and isinstance(result, dict):
            rows = result.get("rows")
            if isinstance(rows, list) and len(rows) == 1:
                row = rows[0]
                if isinstance(row, dict):
                    coordinates = [({"path": ["rows", 0, key]}, key) for key in row]
                elif isinstance(row, list):
                    coordinates = [
                        ({"path": ["rows", 0, index]}, column)
                        for index, column in enumerate(artifact.columns)
                        if index < len(row)
                    ]
        elif isinstance(result, dict):

            def walk(field, value, path=()):
                if isinstance(value, dict) and len(path) < 4:
                    for key, child in value.items():
                        if isinstance(key, str):
                            yield from walk(field, child, (*path, key))
                elif not isinstance(value, (dict, list)):
                    yield (
                        {"field": field, "path": list(path)},
                        path[-1] if path else field,
                    )

            coordinates = [
                coordinate
                for field, value in result.items()
                if isinstance(field, str)
                for coordinate in walk(field, value)
            ][:80]
        for selector, field_name in coordinates:
            try:
                self.register(
                    session_id,
                    artifact,
                    selector,
                    label=field_name,
                    _artifact_persisted=True,
                )
            except (ValueError, TypeError):
                continue


class SessionArtifactSink(InMemoryArtifactSink):
    """Preserve run ownership checks and expose only this session's prior evidence."""

    def __init__(self, context, catalog: EvidenceCatalog, *, include_prior=False):
        super().__init__(context)
        self.catalog = catalog
        self.include_prior = include_prior

    def record(self, artifact):
        if self.include_prior:
            self.snapshot()
        super().record(artifact)
        self._persist(artifact)

    def restore_artifact(self, artifact):
        super().restore_artifact(artifact)
        self._persist(artifact)

    def _persist(self, artifact):
        captured = next(
            item
            for item in super().snapshot()
            if item.artifact_id == artifact.artifact_id
        )
        try:
            self.catalog.save_artifact(self.context.conv_uid, captured)
            self.catalog.register_observed_scalars(self.context.conv_uid, captured)
        except (OSError, sqlite3.Error):
            # The report can still cite the validated in-memory artifact.
            logger.warning("Session evidence catalog write failed", exc_info=True)

    def snapshot(self):
        if not self.include_prior:
            return super().snapshot()
        try:
            persisted = self.catalog.list_artifacts(self.context.conv_uid)
        except (OSError, sqlite3.Error):
            logger.warning("Session evidence catalog read failed", exc_info=True)
            persisted = []
        known = {item.artifact_id for item in super().snapshot()}
        for artifact in persisted:
            if artifact.artifact_id not in known:
                super().restore_artifact(artifact)
                known.add(artifact.artifact_id)
        return super().snapshot()
