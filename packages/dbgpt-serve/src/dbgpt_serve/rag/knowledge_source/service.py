"""Knowledge source service: bindings + the sync engine."""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from dbgpt.component import SystemApp
from dbgpt_serve.rag.knowledge_source.crypto import decrypt_config
from dbgpt_serve.rag.knowledge_source.ingest import (
    IngestResult,
    KnowledgeSourceIngestor,
)
from dbgpt_serve.rag.knowledge_source.models import (
    KnowledgeSourceDao,
    KnowledgeSourceSyncLogDao,
)

logger = logging.getLogger(__name__)


class KnowledgeSourceService:
    def __init__(self, system_app: SystemApp):
        self._system_app = system_app
        self._dao = KnowledgeSourceDao()
        self._log_dao = KnowledgeSourceSyncLogDao()

    @property
    def rag_service(self):
        from ..service.service import Service

        return Service.get_instance(self._system_app)

    # -- connector helpers -------------------------------------------------
    @staticmethod
    def connector_for(source_type: str):
        from dbgpt_ext.knowledge_source.registry import get_source_connector

        return get_source_connector(source_type)()

    async def validate_config(self, source_type: str, config: Dict[str, str]) -> None:
        await self.connector_for(source_type).validate(config or {})

    def list_connector_metas(self) -> Dict[str, Any]:
        from dbgpt_ext.knowledge_source.registry import (
            ensure_source_connectors_loaded,
            list_source_connector_metas,
        )

        ensure_source_connectors_loaded()
        return {
            t: {
                "name": m.name,
                "icon": m.icon,
                "description": m.description,
                "supports_incremental": m.supports_incremental,
                "resource_noun": m.resource_noun,
                "auth_fields": [
                    {
                        "key": f.key,
                        "label": f.label,
                        "required": f.required,
                        "secret": f.secret,
                        "placeholder": f.placeholder,
                        "hint": f.hint,
                    }
                    for f in m.auth_fields
                ],
            }
            for t, m in list_source_connector_metas().items()
        }

    # -- sync engine ---------------------------------------------------------
    async def run_sync(self, source_id: int, trigger: str = "manual") -> Dict[str, Any]:
        """Claim + run one sync of a binding (single worker P0)."""
        from dbgpt_ext.knowledge_source.base import SyncCursor

        source = self._dao.try_claim(source_id)
        if source is None:
            return {"status": "busy", "source_id": source_id}

        started_at = datetime.now()
        stats = {
            IngestResult.CREATED: 0,
            IngestResult.UPDATED: 0,
            IngestResult.SKIPPED: 0,
            "failed": 0,
            "deleted": 0,
        }
        error: Optional[str] = None
        mapping: Dict[str, int] = {}
        cursor_snapshot: Dict[str, str] = {}
        # external ids actually present at the source this run — used for
        # the deletion reconcile when ``sync_deletions`` is on (WeKnora
        # tombstone semantics); only meaningful for full passes
        seen_ids: set = set()
        try:
            from dbgpt_ext.knowledge_source.base import SyncCursor

            cfg = decrypt_config(source.config, self._system_app)
            connector = self.connector_for(source.type)
            mapping = json.loads(source.mapping_json or "{}") or {}
            cursor = SyncCursor.from_dict(
                json.loads(source.last_sync_cursor) if source.last_sync_cursor else None
            )
            resource_ids = (
                json.loads(source.target_resource_ids)
                if source.target_resource_ids
                else []
            )
            ingestor = KnowledgeSourceIngestor(self.rag_service)

            async def on_item(item):
                seen_ids.add(item.external_id)
                try:
                    action = await ingestor.ingest_item(
                        source.space_id, source, item, mapping
                    )
                    stats[action] = stats.get(action, 0) + 1
                except Exception as exc:  # noqa: BLE001 - one bad doc ≠ dead sync
                    stats["failed"] += 1
                    logger.error(
                        f"knowledge-source {source.id}: ingest "
                        f"{item.external_id} failed: {exc}\n" + traceback.format_exc()
                    )

            incremental = source.sync_mode == "incremental" and bool(cursor.to_dict())
            if incremental:
                new_cursor = await connector.fetch_incremental(
                    cfg, resource_ids, cursor, on_item
                )
            else:
                new_cursor = await connector.fetch_all(
                    cfg, resource_ids, on_item, cursor
                )
            cursor_snapshot = new_cursor.to_dict()
        except Exception as exc:  # noqa: BLE001 - sync-level failure
            error = f"{type(exc).__name__}: {exc}"
            logger.error(
                f"knowledge-source {source.id} sync failed: {error}\n"
                + traceback.format_exc()
            )

        # deletion reconcile: only a FULL listing can prove a source removal
        # (an incremental pass only reports the changed subset). WeKnora
        # tombstone semantics, scoped likewise.
        if source.sync_deletions and not error and not incremental:
            stale = [e for e in list(mapping.keys()) if e not in seen_ids]

            for external_id in stale:
                doc_id = mapping.pop(external_id, None)
                if doc_id is None:
                    continue
                try:
                    await self.rag_service.delete_document(str(doc_id))
                    stats["deleted"] += 1
                    logger.info(
                        f"knowledge-source {source.id}: deleted doc {doc_id} "
                        f"(source removal of {external_id})"
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        f"knowledge-source {source.id}: delete doc "
                        f"{doc_id} failed: {exc}"
                    )

        finished_at = datetime.now()
        summary = {
            "status": "failed" if error else "success",
            "trigger": trigger,
            "mode": source.sync_mode if source.sync_mode else "full",
            "items_created": stats[IngestResult.CREATED],
            "items_updated": stats[IngestResult.UPDATED],
            "items_skipped": stats[IngestResult.SKIPPED],
            "items_failed": stats["failed"],
            "items_deleted": stats["deleted"],
            "error": error,
            "started_at": started_at,
            "finished_at": finished_at,
        }
        self._log_dao.append(
            {"source_id": source.id, "space_id": source.space_id, **summary}
        )
        self._dao.release_claim(
            source.id,
            ok=not error,
            cursor_json=json.dumps(cursor_snapshot, ensure_ascii=False),
            mapping_json=json.dumps(mapping, ensure_ascii=False),
            result_json=json.dumps(
                {k: v for k, v in summary.items() if k != "source_id"},
                ensure_ascii=False,
                default=str,
            ),
            error=error,
            is_error_state=True,
        )
        return summary

    # -- binding CRUD passthrough ---------------------------------------------
    def list_by_space(self, space_id: int) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._dao.list_by_space(space_id)]

    def get(self, source_id: int) -> Optional[Dict[str, Any]]:
        row = self._dao.get_source(source_id)
        return row.to_dict() if row else None

    async def create(self, **kwargs) -> Dict[str, Any]:
        # validate against the connector contract before persisting
        await self.validate_config(kwargs["type"], kwargs.get("plain_config") or {})
        from dbgpt_serve.rag.knowledge_source.crypto import encrypt_config

        row = self._dao.create_source(
            {
                "space_id": kwargs["space_id"],
                "name": kwargs.get("name"),
                "type": kwargs["type"],
                "config": encrypt_config(
                    kwargs.get("plain_config") or {}, self._system_app
                ),
                "target_resource_ids": json.dumps(
                    kwargs.get("target_resource_ids") or []
                ),
                "interval_minutes": kwargs.get("interval_minutes") or 0,
                "sync_mode": kwargs.get("sync_mode") or "incremental",
                "conflict_strategy": kwargs.get("conflict_strategy") or "overwrite",
                "sync_deletions": kwargs.get("sync_deletions"),
            }
        )
        return row.to_dict()

    def update(self, source_id: int, updates: Dict[str, Any]) -> None:
        plain = updates.pop("plain_config", None)
        if plain is not None:
            from dbgpt_serve.rag.knowledge_source.crypto import encrypt_config

            updates["config"] = encrypt_config(plain, self._system_app)
        self._dao.update_source(source_id, updates)

    def delete(self, source_id: int) -> bool:
        return self._dao.delete_source(source_id)

    async def list_resources(
        self, source_id: int, parent_id: str = ""
    ) -> List[Dict[str, Any]]:
        row = self._dao.get_source(source_id)
        if row is None:
            raise ValueError(f"knowledge source {source_id} not found")
        cfg = decrypt_config(row.config, self._system_app)
        connector = self.connector_for(row.type)
        resources = await connector.list_resources(cfg, parent_id)
        return [
            {
                "external_id": r.external_id,
                "title": r.title,
                "parent_id": r.parent_id,
                "has_children": r.has_children,
                "resource_type": r.resource_type,
            }
            for r in resources
        ]

    def list_logs(self, source_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        logs = self._log_dao.list_by_source(source_id, limit)
        return [self._log_dao.to_dict(log) for log in logs]


_current_ks_service: Optional[KnowledgeSourceService] = None


def get_knowledge_source_service(system_app: SystemApp) -> KnowledgeSourceService:
    """Process-wide singleton keyed on the SystemApp instance."""
    global _current_ks_service
    if _current_ks_service is None:
        _current_ks_service = KnowledgeSourceService(system_app)
    return _current_ks_service
