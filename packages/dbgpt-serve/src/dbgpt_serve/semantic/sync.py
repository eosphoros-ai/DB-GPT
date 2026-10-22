"""L1 metadata sync + drift detection (phase 1).

``SemanticSyncService`` introspects a live connector and upserts the L1
snapshot (``sem_table`` / ``sem_column``). Schema drift (dropped/renamed or
re-typed objects) marks the affected rows ``deleted`` and flips dependent L2
entries to ``stale`` so they re-enter the review queue instead of silently
serving wrong semantics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from dbgpt_serve.semantic.models import (
    SemColumnDao,
    SemColumnEntity,
    SemDatasourceDao,
    SemDatasourceEntity,
    SemEntryDao,
    SemTableDao,
    SemTableEntity,
)

logger = logging.getLogger(__name__)

DEFAULT_WHITELIST_LIMIT = 42


@dataclass
class SyncReport:
    """Counters returned by :meth:`SemanticSyncService.sync`."""

    ds_id: int = 0
    tables_added: int = 0
    tables_updated: int = 0
    tables_deleted: int = 0
    columns_added: int = 0
    columns_updated: int = 0
    columns_deleted: int = 0
    entries_staled: int = 0
    whitelist_applied: int = 0


def _table_comments(connector: Any, db_name: str) -> Dict[str, str]:
    try:
        raw = connector.get_table_comments(db_name) or []
    except Exception as e:  # noqa: BLE001 - comments are best-effort
        logger.warning(f"get_table_comments failed: {e}")
        return {}
    out: Dict[str, str] = {}
    for item in raw:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            out[str(item[0])] = str(item[1] or "")
        elif isinstance(item, dict):
            name = item.get("name") or item.get("table_name")
            if name:
                out[str(name)] = str(item.get("comment") or "")
    return out


class SemanticSyncService:
    """Sync L1 metadata from a connector into the semantic meta DB."""

    def __init__(
        self,
        ds_dao: Optional[SemDatasourceDao] = None,
        table_dao: Optional[SemTableDao] = None,
        column_dao: Optional[SemColumnDao] = None,
        entry_dao: Optional[SemEntryDao] = None,
    ) -> None:
        self._ds_dao = ds_dao or SemDatasourceDao()
        self._table_dao = table_dao or SemTableDao()
        self._column_dao = column_dao or SemColumnDao()
        self._entry_dao = entry_dao or SemEntryDao()

    def ensure_space(
        self, conn_id: str, conn_name: str, db_type: str
    ) -> SemDatasourceEntity:
        """Idempotently register a not_activated semantic space."""
        return self._ds_dao.ensure_space(conn_id, conn_name, db_type)

    def sync(self, conn_id: str, connector: Any) -> SyncReport:
        """Full L1 snapshot sync with drift detection."""
        space = self.ensure_space(
            conn_id,
            conn_id,
            str(getattr(connector, "db_type", "") or ""),
        )
        report = SyncReport(ds_id=space.id)
        now = datetime.utcnow()
        db_name = self._safe(connector.get_current_db_name, default="")
        comments = _table_comments(connector, db_name) if db_name else {}
        snapshot: List[str] = list(connector.get_table_names() or [])

        session = self._table_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            space = session.merge(space)
            existing = {
                t.table_name: t
                for t in self._table_dao.list_by_ds(space.id)
                if t.status != "deleted"
            }
            seen: Dict[str, SemTableEntity] = {}
            for name in snapshot:
                table = existing.get(name)
                comment = comments.get(name)
                if table is None:
                    table = SemTableEntity(
                        ds_id=space.id,
                        table_name=name,
                        table_comment=comment,
                        last_sync_at=now,
                    )
                    session.add(table)
                    session.flush()
                    report.tables_added += 1
                else:
                    if (comment or "") != (table.table_comment or ""):
                        table.table_comment = comment
                        report.tables_updated += 1
                    table.last_sync_at = now
                    table.status = "active"
                seen[name] = table
                report = self._sync_columns(
                    session, space.id, table, connector, name, now, report
                )
            stale_table_ids: List[int] = []
            for name, table in existing.items():
                if name not in seen:
                    table.status = "deleted"
                    stale_table_ids.append(table.id)
                    report.tables_deleted += 1
            space.table_count = len(seen)
            space.last_sync_at = now
            session.commit()
            report.entries_staled += self._entry_dao.mark_stale(
                space.id, "table", stale_table_ids
            )
        finally:
            session.close()

        if space.status == "not_activated":
            report.whitelist_applied = self.apply_whitelist(space.id)
        return report

    def _sync_columns(
        self,
        session: Any,
        ds_id: int,
        table: SemTableEntity,
        connector: Any,
        table_name: str,
        now: datetime,
        report: SyncReport,
    ) -> SyncReport:
        cols = self._safe(connector.get_columns, table_name, default=[]) or []
        existing = {
            c.column_name: c for c in self._list_columns(session, ds_id, table.id)
        }
        seen_ids: Dict[str, SemColumnEntity] = {}
        stale_col_ids: List[int] = []
        for col in cols:
            name = str(col.get("name"))
            ctype = str(col.get("type") or "")
            comment = col.get("comment")
            is_pk = bool(col.get("is_in_primary_key"))
            column = existing.get(name)
            if column is None:
                column = SemColumnEntity(
                    ds_id=ds_id,
                    table_id=table.id,
                    column_name=name,
                    column_type=ctype,
                    column_comment=comment,
                    is_pk=is_pk,
                    last_sync_at=now,
                )
                session.add(column)
                session.flush()
                report.columns_added += 1
            else:
                changed = (ctype or "") != (column.column_type or "")
                if changed:
                    column.column_type = ctype
                    stale_col_ids.append(column.id)
                    report.columns_updated += 1
                column.column_comment = comment
                column.is_pk = is_pk
                column.status = "active"
                column.last_sync_at = now
            seen_ids[name] = column
        for name, column in existing.items():
            if name not in seen_ids and column.status != "deleted":
                column.status = "deleted"
                stale_col_ids.append(column.id)
                report.columns_deleted += 1
        if stale_col_ids:
            session.commit()
            report.entries_staled += self._entry_dao.mark_stale(
                ds_id, "column", stale_col_ids
            )
        return report

    @staticmethod
    def _list_columns(session: Any, ds_id: int, table_id: int) -> List[SemColumnEntity]:
        return (
            session.query(SemColumnEntity)
            .filter(
                SemColumnEntity.ds_id == ds_id,
                SemColumnEntity.table_id == table_id,
                SemColumnEntity.status != "deleted",
            )
            .all()
        )

    def apply_whitelist(self, ds_id: int, limit: int = DEFAULT_WHITELIST_LIMIT) -> int:
        """P0 sampling proxy: comment coverage first, then name order.

        P1 replaces the ordering with query-history frequency.
        """
        session = self._table_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            tables = (
                session.query(SemTableEntity)
                .filter(
                    SemTableEntity.ds_id == ds_id,
                    SemTableEntity.status == "active",
                )
                .all()
            )
            tables.sort(
                key=lambda t: (
                    not bool(t.table_comment),
                    -(t.row_count_est or 0),
                    t.table_name,
                )
            )
            chosen = 0
            for table in tables:
                table.is_whitelisted = chosen < limit
                chosen += 1 if table.is_whitelisted else 0
            session.commit()
            return min(chosen, limit)
        finally:
            session.close()

    @staticmethod
    def _safe(fn: Any, *args: Any, default: Any = None, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - introspection is best-effort
            logger.warning(f"connector introspection failed: {e}")
            return default


def semantic_auto_register(system_app: Any, db_name: str, db_type: str) -> None:
    """Hook target: register the space now, sync L1 in the background."""
    service = SemanticSyncService()
    service.ensure_space(db_name, db_name, db_type)
    try:
        from dbgpt.component import ComponentType
        from dbgpt.util.executor_utils import ExecutorFactory

        executor = system_app.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()
        executor.submit(_bg_sync, system_app, db_name)
    except Exception as e:  # noqa: BLE001 - hook must never break the caller
        logger.warning(f"semantic background sync skipped: {e}")


def _bg_sync(system_app: Any, db_name: str) -> None:
    try:
        from dbgpt.component import ComponentType
        from dbgpt_serve.datasource.manages.connector_manager import ConnectorManager

        manager = system_app.get_component(ComponentType.CONNECTOR, ConnectorManager)
        connector = manager.get_connector(db_name)
        SemanticSyncService().sync(db_name, connector)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"semantic sync failed for {db_name}: {e}")
