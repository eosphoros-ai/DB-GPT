"""L4 join graph discovery (FK direct + naming heuristics).

- FK edges come from the connector's SQLAlchemy inspector when available:
  ``kind=fk``, ``status=active`` (declared facts, no review needed).
- Naming heuristics (``<table>_id`` / ``<table_singular>_id`` columns pointing
  at another table's PK) produce ``kind=inferred``, ``status=draft`` edges
  (confidence 0.6) that wait for human calibration in the review queue.

Discovery is idempotent: edges are deduped on the (left, right) column pair.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from dbgpt_serve.semantic.models import (
    SemColumnDao,
    SemRelationEntity,
    SemTableDao,
)

logger = logging.getLogger(__name__)


class JoinDiscoverer:
    """Populate ``sem_relation`` for one semantic space."""

    def __init__(
        self,
        table_dao: Optional[SemTableDao] = None,
        column_dao: Optional[SemColumnDao] = None,
    ) -> None:
        self._table_dao = table_dao or SemTableDao()
        self._column_dao = column_dao or SemColumnDao()

    def discover(self, ds_id: int, connector: Optional[Any] = None) -> Dict[str, int]:
        tables = self._table_dao.list_by_ds(ds_id, status="active")
        table_by_id = {t.id: t for t in tables}
        name_to_id = {t.table_name: t.id for t in tables}
        cols_by_table: Dict[int, List[Any]] = {
            t.id: self._column_dao.list_by_table(ds_id, t.id, status="active")
            for t in tables
        }
        counts = {"fk": 0, "inferred": 0, "skipped": 0}
        session = self._table_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            existing = {
                (
                    r.left_table_id,
                    r.left_column_id,
                    r.right_table_id,
                    r.right_column_id,
                )
                for r in session.query(SemRelationEntity)
                .filter(SemRelationEntity.ds_id == ds_id)
                .all()
            }

            def col_id(table_id: int, name: str) -> Optional[int]:
                for c in cols_by_table.get(table_id, []):
                    if c.column_name == name:
                        return c.id
                return None

            def pk_col_id(table_id: int) -> Optional[int]:
                for c in cols_by_table.get(table_id, []):
                    if c.is_pk or c.column_name == "id":
                        return c.id
                return None

            def add_edge(
                lt: int,
                lc: int,
                rt: int,
                rc: int,
                kind: str,
                status: str,
                confidence: float,
                provenance: str,
            ) -> None:
                key: Tuple[int, int, int, int] = (lt, lc, rt, rc)
                if key in existing:
                    counts["skipped"] += 1
                    return
                existing.add(key)
                session.add(
                    SemRelationEntity(
                        ds_id=ds_id,
                        left_table_id=lt,
                        left_column_id=lc,
                        right_table_id=rt,
                        right_column_id=rc,
                        relation_type=kind,
                        join_condition=f"{table_by_id[lt].table_name}."
                        f"{_name(cols_by_table, lt, lc)} = "
                        f"{table_by_id[rt].table_name}."
                        f"{_name(cols_by_table, rt, rc)}",
                        confidence=confidence,
                        status=status,
                        provenance=provenance,
                    )
                )
                counts["fk" if kind == "fk" else "inferred"] += 1

            # 1) declared FKs from the connector inspector (best-effort)
            inspector = getattr(connector, "_inspector", None) if connector else None
            if inspector is not None:
                for table in tables:
                    try:
                        fks = inspector.get_foreign_keys(table.table_name) or []
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"get_foreign_keys failed: {e}")
                        continue
                    for fk in fks:
                        rt = name_to_id.get(fk.get("referred_table"))
                        constrained = fk.get("constrained_columns") or []
                        referred = fk.get("referred_columns") or []
                        if not rt or not constrained or not referred:
                            continue
                        lc = col_id(table.id, constrained[0])
                        rc = col_id(rt, referred[0])
                        if lc and rc:
                            add_edge(
                                table.id, lc, rt, rc, "fk", "active", 1.0, "fk_sync"
                            )

            # 2) naming heuristics: <table>_id / <singular>_id -> that table PK
            for table in tables:
                for col in cols_by_table.get(table.id, []):
                    low = (col.column_name or "").lower()
                    if not low.endswith("_id"):
                        continue
                    ref = low[: -len("_id")]
                    rt = name_to_id.get(ref) or name_to_id.get(ref + "s")
                    if not rt or rt == table.id:
                        continue
                    rc = pk_col_id(rt)
                    if not rc:
                        continue
                    add_edge(
                        table.id, col.id, rt, rc, "inferred", "draft", 0.6, "inferred"
                    )
            session.commit()
        finally:
            session.close()
        return counts


def _name(cols_by_table: Dict[int, List[Any]], table_id: int, col_id: int) -> str:
    for c in cols_by_table.get(table_id, []):
        if c.id == col_id:
            return c.column_name
    return f"col#{col_id}"
