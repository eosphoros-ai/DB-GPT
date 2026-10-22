"""Semantic center governance service (phase 2).

Space lifecycle (not_activated -> activated), draft review (confirm / modify /
reject), metric caliber versioning, and coverage stats. Publishing delegates
chunk rendering + sink writes to :class:`SemanticPublisher`; drafts never
enter retrieval until published.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from dbgpt_serve.semantic.models import (
    SemColumnDao,
    SemDatasourceDao,
    SemEntryDao,
    SemEntryEntity,
    SemExampleDao,
    SemMetricDao,
    SemMetricEntity,
    SemMetricVersionDao,
    SemMetricVersionEntity,
    SemRuleDao,
    SemTableDao,
    dump_json,
    filters_to_dict,
)
from dbgpt_serve.semantic.publisher import SemanticPublisher
from dbgpt_serve.semantic.sync import SemanticSyncService

logger = logging.getLogger(__name__)


class SemanticService:
    """Governance facade over the semantic meta DB."""

    def __init__(
        self,
        sync_service: Optional[SemanticSyncService] = None,
        publisher: Optional[SemanticPublisher] = None,
        ds_dao: Optional[SemDatasourceDao] = None,
        table_dao: Optional[SemTableDao] = None,
        column_dao: Optional[SemColumnDao] = None,
        entry_dao: Optional[SemEntryDao] = None,
        metric_dao: Optional[SemMetricDao] = None,
        metric_version_dao: Optional[SemMetricVersionDao] = None,
        example_dao: Optional[SemExampleDao] = None,
        rule_dao: Optional[SemRuleDao] = None,
    ) -> None:
        self._sync = sync_service or SemanticSyncService()
        self._publisher = publisher or SemanticPublisher()
        self._ds_dao = ds_dao or SemDatasourceDao()
        self._table_dao = table_dao or SemTableDao()
        self._column_dao = column_dao or SemColumnDao()
        self._entry_dao = entry_dao or SemEntryDao()
        self._metric_dao = metric_dao or SemMetricDao()
        self._metric_version_dao = metric_version_dao or SemMetricVersionDao()
        self._example_dao = example_dao or SemExampleDao()
        self._rule_dao = rule_dao or SemRuleDao()
        # Optional hook for the phase-3 annotator (LLM draft generation).
        self.draft_hook: Optional[Callable[[int], None]] = None

    # ---- spaces ----
    def list_spaces(self) -> List[Dict[str, Any]]:
        return [self._space_dict(s) for s in self._ds_dao.list_spaces()]

    def get_space(self, ds_id: int) -> Optional[Dict[str, Any]]:
        session = self._ds_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            from dbgpt_serve.semantic.models import SemDatasourceEntity

            space = (
                session.query(SemDatasourceEntity)
                .filter(SemDatasourceEntity.id == ds_id)
                .first()
            )
            return self._space_dict(space) if space else None
        finally:
            session.close()

    def activate(
        self,
        ds_id: int,
        sampling_limit: int = 42,
        run_draft_generation: bool = False,
        embedding_model: str = "bge-large-zh",
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        """One-click governance activation (cost items are opt-in)."""
        session = self._ds_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            from dbgpt_serve.semantic.models import SemDatasourceEntity

            space = (
                session.query(SemDatasourceEntity)
                .filter(SemDatasourceEntity.id == ds_id)
                .first()
            )
            if not space:
                raise ValueError(f"semantic space {ds_id} not found")
            space.status = "activated"
            space.activated_at = datetime.utcnow()
            space.embedding_model = embedding_model
            space.user_name = user or space.user_name
            session.commit()
        finally:
            session.close()
        whitelist = self._sync.apply_whitelist(ds_id, sampling_limit)
        if run_draft_generation:
            if self.draft_hook:
                self.draft_hook(ds_id)
            else:
                logger.info(
                    "draft generation requested for space %s; annotator lands "
                    "in phase 3, skipped for now",
                    ds_id,
                )
        return {"ds_id": ds_id, "status": "activated", "whitelist": whitelist}

    # ---- review & publish ----
    def review_entry(
        self,
        entry_id: int,
        action: str,
        user: Optional[str] = None,
        updates: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """confirm | modify | reject a semantic annotation draft."""
        entry = self._entry_dao.get(entry_id)
        if not entry:
            raise ValueError(f"entry {entry_id} not found")
        if action == "reject":
            entry.status = "rejected"
            self._commit_entry(entry)
            return {"entry_id": entry_id, "status": "rejected"}
        if action == "modify":
            for key in ("entry_comment", "synonyms", "entry_definition"):
                if updates and key in updates:
                    value = updates[key]
                    setattr(
                        entry, key, dump_json(value) if key == "synonyms" else value
                    )
            entry.status = "draft"
            entry.version += 1
            self._commit_entry(entry)
            return {"entry_id": entry_id, "status": "draft", "version": entry.version}
        if action != "confirm":
            raise ValueError(f"unsupported review action: {action}")
        entry.status = "published"
        entry.publish_version = entry.version
        entry.last_publish_at = datetime.utcnow()
        entry.user_name = user or entry.user_name
        self._commit_entry(entry)
        table_name, column_name = self._resolve_target(entry)
        space = self._ds_dao.get(entry.ds_id)
        chunk_id = self._publisher.publish_entry(
            entry.ds_id,
            space.space_name if space else f"semantic::{entry.ds_id}",
            entry,
            table_name or "",
            column_name,
            user,
        )
        return {"entry_id": entry_id, "status": "published", "chunk_id": chunk_id}

    def create_metric(
        self,
        ds_id: int,
        payload: Dict[str, Any],
        user: Optional[str] = None,
        provenance: str = "manual",
        suite_id: Optional[str] = None,
    ) -> SemMetricEntity:
        metric = SemMetricEntity(
            ds_id=ds_id,
            metric_name=payload["metric_name"],
            metric_comment=payload.get("metric_comment"),
            metric_type=payload.get("metric_type", "atomic"),
            metric_definition=payload.get("metric_definition"),
            formula=payload.get("formula"),
            base_metrics=dump_json(payload.get("base_metrics")),
            dimensions=dump_json(payload.get("dimensions")),
            status="draft",
            version=0,
            provenance=provenance,
            suite_id=suite_id,
            user_name=user,
        )
        session = self._metric_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            session.add(metric)
            session.commit()
            return metric
        finally:
            session.close()

    def publish_metric(
        self,
        metric_id: int,
        user: Optional[str] = None,
        change_note: str = "",
    ) -> Dict[str, Any]:
        """Bump the caliber version, snapshot it, and publish the chunk."""
        metric = self._metric_dao.get(metric_id)
        if not metric:
            raise ValueError(f"metric {metric_id} not found")
        new_version = metric.version + 1
        version_row = SemMetricVersionEntity(
            metric_id=metric.id,
            version=new_version,
            metric_definition=metric.metric_definition,
            formula=metric.formula,
            base_metrics=metric.base_metrics,
            dimensions=metric.dimensions,
            change_note=change_note,
            published_at=datetime.utcnow(),
            published_by=user,
        )
        metric.version = new_version
        metric.publish_version = new_version
        metric.status = "published"
        metric.last_publish_at = datetime.utcnow()
        session = self._metric_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            session.merge(metric)
            session.add(version_row)
            session.commit()
        finally:
            session.close()
        space = self._ds_dao.get(metric.ds_id)
        chunk_id = self._publisher.publish_metric(
            metric.ds_id,
            space.space_name if space else f"semantic::{metric.ds_id}",
            metric,
            user,
            change_note,
        )
        return {"metric_id": metric_id, "version": new_version, "chunk_id": chunk_id}

    # ---- observability ----
    def coverage(self, ds_id: int) -> Dict[str, Any]:
        tables = self._table_dao.list_by_ds(ds_id, status="active")
        entries = self._entry_dao.list_by_ds(ds_id)
        metrics = self._metric_dao.list_by_ds(ds_id)
        entry_status: Dict[str, int] = {}
        for entry in entries:
            entry_status[entry.status] = entry_status.get(entry.status, 0) + 1
        metric_status: Dict[str, int] = {}
        for metric in metrics:
            metric_status[metric.status] = metric_status.get(metric.status, 0) + 1
        annotated = sum(1 for t in tables if any(e.target_id == t.id for e in entries))
        total = len(tables) or 1
        return {
            "ds_id": ds_id,
            "tables": len(tables),
            "whitelisted": sum(1 for t in tables if t.is_whitelisted),
            "tables_annotated": annotated,
            "coverage_pct": round(100.0 * annotated / total, 1),
            "entries": entry_status,
            "metrics": metric_status,
        }

    # ---- list passthroughs (S7 API) ----
    def list_tables(self, ds_id: int, status: str = "active") -> List[Dict[str, Any]]:
        keys = [
            "id",
            "table_name",
            "table_comment",
            "table_type",
            "row_count_est",
            "is_whitelisted",
            "is_sensitive",
            "status",
        ]
        tables = self._table_dao.list_by_ds(ds_id, status=status)
        return [filters_to_dict(t, keys) for t in tables]

    def list_columns(self, ds_id: int, table_id: int) -> List[Dict[str, Any]]:
        keys = [
            "id",
            "column_name",
            "column_type",
            "column_comment",
            "is_pk",
            "is_enum",
            "status",
        ]
        cols = self._column_dao.list_by_table(ds_id, table_id)
        return [filters_to_dict(c, keys) for c in cols]

    def list_entries(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        keys = [
            "id",
            "entry_type",
            "target_id",
            "entry_name",
            "entry_comment",
            "synonyms",
            "status",
            "version",
            "provenance",
            "publish_version",
        ]
        entries = self._entry_dao.list_by_ds(ds_id, status=status)
        return [filters_to_dict(e, keys) for e in entries]

    def list_metrics(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        keys = [
            "id",
            "metric_name",
            "metric_comment",
            "metric_type",
            "formula",
            "dimensions",
            "status",
            "version",
            "provenance",
            "suite_id",
            "publish_version",
        ]
        metrics = self._metric_dao.list_by_ds(ds_id, status=status)
        return [filters_to_dict(m, keys) for m in metrics]

    def list_examples(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        session = self._example_dao.get_raw_session()
        try:
            from dbgpt_serve.semantic.models import SemExampleEntity

            q = session.query(SemExampleEntity).filter(SemExampleEntity.ds_id == ds_id)
            if status:
                q = q.filter(SemExampleEntity.status == status)
            rows = q.all()
            keys = [
                "id",
                "example_name",
                "question",
                "sql_text",
                "source",
                "use_count",
                "status",
            ]
            return [filters_to_dict(r, keys) for r in rows]
        finally:
            session.close()

    def list_relations(
        self, ds_id: int, status: str = "active"
    ) -> List[Dict[str, Any]]:
        session = self._rule_dao.get_raw_session()
        try:
            from dbgpt_serve.semantic.models import SemRelationEntity

            rows = (
                session.query(SemRelationEntity)
                .filter(
                    SemRelationEntity.ds_id == ds_id,
                    SemRelationEntity.status == status,
                )
                .all()
            )
            keys = [
                "id",
                "left_table_id",
                "left_column_id",
                "right_table_id",
                "right_column_id",
                "relation_type",
                "join_condition",
                "confidence",
            ]
            return [filters_to_dict(r, keys) for r in rows]
        finally:
            session.close()

    def list_rules(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        keys = [
            "id",
            "rule_name",
            "rule_type",
            "rule_definition",
            "rule_condition",
            "rule_action",
            "priority",
            "status",
        ]
        rules = self._rule_dao.list_by_ds(ds_id, status=status)
        return [filters_to_dict(r, keys) for r in rules]

    def set_rule_status(self, rule_id: int, status: str) -> Dict[str, Any]:
        session = self._rule_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            from dbgpt_serve.semantic.models import SemRuleEntity

            rule = (
                session.query(SemRuleEntity).filter(SemRuleEntity.id == rule_id).first()
            )
            if not rule:
                raise ValueError(f"rule {rule_id} not found")
            rule.status = status
            session.commit()
            return {"rule_id": rule_id, "status": rule.status}
        finally:
            session.close()

    def create_entry(
        self,
        ds_id: int,
        payload: Dict[str, Any],
        user: Optional[str] = None,
        provenance: str = "manual",
    ) -> Dict[str, Any]:
        from dbgpt_serve.semantic.models import SemEntryEntity, dump_json

        entry = SemEntryEntity(
            ds_id=ds_id,
            entry_type=payload["entry_type"],
            target_id=payload.get("target_id"),
            entry_name=payload.get("entry_name"),
            entry_comment=payload.get("entry_comment"),
            synonyms=dump_json(payload.get("synonyms")),
            entry_definition=payload.get("entry_definition"),
            status="draft",
            provenance=provenance,
            user_name=user,
        )
        session = self._entry_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            session.add(entry)
            session.commit()
            return {"id": entry.id, "status": entry.status}
        finally:
            session.close()

    # ---- internals ----
    def _commit_entry(self, entry: SemEntryEntity) -> None:
        session = self._entry_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            session.merge(entry)
            session.commit()
        finally:
            session.close()

    def _resolve_target(self, entry: SemEntryEntity) -> Any:
        session = self._table_dao.get_raw_session()
        try:
            from dbgpt_serve.semantic.models import SemColumnEntity, SemTableEntity

            if entry.entry_type == "column":
                column = (
                    session.query(SemColumnEntity)
                    .filter(SemColumnEntity.id == entry.target_id)
                    .first()
                )
                if not column:
                    return None, None
                table = (
                    session.query(SemTableEntity)
                    .filter(SemTableEntity.id == column.table_id)
                    .first()
                )
                return (table.table_name if table else None), column.column_name
            table = (
                session.query(SemTableEntity)
                .filter(SemTableEntity.id == entry.target_id)
                .first()
            )
            return (table.table_name if table else None), None
        finally:
            session.close()

    @staticmethod
    def _space_dict(space: Any) -> Dict[str, Any]:
        return {
            "id": space.id,
            "conn_id": space.conn_id,
            "conn_name": space.conn_name,
            "db_type": space.db_type,
            "status": space.status,
            "space_name": space.space_name,
            "embedding_model": space.embedding_model,
            "table_count": space.table_count,
            "chunk_count": space.chunk_count,
            "last_sync_at": space.last_sync_at.isoformat()
            if space.last_sync_at
            else None,
        }
