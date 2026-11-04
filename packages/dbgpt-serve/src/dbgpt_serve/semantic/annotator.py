"""L2 semantic annotation draft generation (S3, phase 3).

Produces ``sem_entry`` drafts (table/column descriptions, enum semantics,
synonyms) from L1 facts plus an optional LLM. Drafts **never enter retrieval**
until human-confirm (see :mod:`dbgpt_serve.semantic.publisher`).

``llm_client`` is a sync callable ``prompt -> str`` returning JSON; the
production wiring (DefaultLLMClient bridge via ``asyncio.to_thread``) lands in
P1. Heuristic mode keeps the pipeline usable without a model server:

- column has comment  -> description draft, provenance=auto,   conf 0.95
- enum-like name      -> enum draft "待业务确认",   provenance=auto,   conf 0.60
- key/time/bool name  -> typed draft,               provenance=auto,   conf 0.70
- otherwise           -> name-derived draft,        provenance=auto,   conf 0.50
- with llm_client     -> LLM JSON wins when present, provenance=llm_draft
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from dbgpt_serve.semantic.models import (
    SemColumnDao,
    SemEntryDao,
    SemEntryEntity,
    SemTableDao,
    dump_json,
)

logger = logging.getLogger(__name__)

ENUM_HINTS = ("status", "state", "type", "channel", "flag", "category")
TIME_HINTS = ("_at", "_time", "date", "_dt", "created", "updated")
KEY_HINTS = ("_id", "_code", "_no", "uuid")
BOOL_HINTS = ("is_", "has_", "can_")

LLM_ENTRY_PROMPT = """你是数据语义标注器。给定表 {table} 及其列
（含类型/注释/采样语义），为每一列产出业务描述、
同义词（0-3 个）、枚举语义（若为枚举列）。
只输出 JSON：
{{"columns":[{{"column":...,"comment":...,"synonyms":[...],"enum":...}}]}}
列清单：{columns}"""


def _heuristic_column(name: str, ctype: str) -> Tuple[str, float]:
    low = (name or "").lower()
    if low.startswith(BOOL_HINTS):
        return f"布尔标记列 {name}（0/1 语义待业务确认）", 0.7
    if any(h in low for h in ENUM_HINTS):
        return f"枚举列 {name}：取值语义待业务确认（如 0/1/2 状态码）", 0.6
    if any(h in low for h in TIME_HINTS):
        return f"时间列 {name}（{ctype or 'unknown'}），时间口径候选字段", 0.7
    if any(h in low for h in KEY_HINTS):
        return f"键列 {name}：主键/外键标识，join 路径见血缘", 0.7
    return f"列 {name}（{ctype or 'unknown'}）：业务语义待补充", 0.5


class SemanticAnnotator:
    """Generate L2 drafts for one semantic space (idempotent)."""

    def __init__(
        self,
        table_dao: Optional[SemTableDao] = None,
        column_dao: Optional[SemColumnDao] = None,
        entry_dao: Optional[SemEntryDao] = None,
    ) -> None:
        self._table_dao = table_dao or SemTableDao()
        self._column_dao = column_dao or SemColumnDao()
        self._entry_dao = entry_dao or SemEntryDao()

    def generate_drafts(
        self,
        ds_id: int,
        llm_client: Optional[Callable[[str], str]] = None,
    ) -> Dict[str, int]:
        tables = self._table_dao.list_by_ds(ds_id, status="active")
        existing = {
            (e.entry_type, e.target_id) for e in self._entry_dao.list_by_ds(ds_id)
        }
        counts = {"table_entries": 0, "column_entries": 0, "skipped": 0}
        session = self._entry_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            for table in tables:
                if ("table", table.id) not in existing:
                    comment = table.table_comment or ""
                    conf = 0.95 if comment else 0.5
                    session.add(
                        SemEntryEntity(
                            ds_id=ds_id,
                            entry_type="table",
                            target_id=table.id,
                            entry_name=table.table_name,
                            entry_comment=comment
                            or f"表 {table.table_name}：业务含义待补充",
                            status="draft",
                            confidence=conf,
                            provenance="auto",
                        )
                    )
                    counts["table_entries"] += 1
                else:
                    counts["skipped"] += 1
                columns = self._column_dao.list_by_table(ds_id, table.id, "active")
                llm_map = self._llm_columns(llm_client, table.table_name, columns)
                for column in columns:
                    if ("column", column.id) in existing:
                        counts["skipped"] += 1
                        continue
                    llm = llm_map.get(column.column_name)
                    if llm:
                        comment = llm.get("comment") or column.column_comment or ""
                        synonyms = llm.get("synonyms") or []
                        provenance = "llm_draft"
                        conf = 0.85
                    elif column.column_comment:
                        comment = column.column_comment
                        synonyms = []
                        provenance = "auto"
                        conf = 0.95
                    else:
                        comment, conf = _heuristic_column(
                            column.column_name, column.column_type or ""
                        )
                        synonyms = []
                        provenance = "auto"
                    session.add(
                        SemEntryEntity(
                            ds_id=ds_id,
                            entry_type="column",
                            target_id=column.id,
                            entry_name=f"{table.table_name}.{column.column_name}",
                            entry_comment=comment,
                            synonyms=dump_json(synonyms) if synonyms else None,
                            status="draft",
                            confidence=conf,
                            provenance=provenance,
                        )
                    )
                    counts["column_entries"] += 1
            session.commit()
        finally:
            session.close()
        return counts

    @staticmethod
    def _llm_columns(
        llm_client: Optional[Callable[[str], str]],
        table_name: str,
        columns: List[Any],
    ) -> Dict[str, Dict[str, Any]]:
        if not llm_client or not columns:
            return {}
        payload = [
            {
                "column": c.column_name,
                "type": c.column_type,
                "comment": c.column_comment,
            }
            for c in columns
        ]
        prompt = LLM_ENTRY_PROMPT.format(table=table_name, columns=json.dumps(payload))
        try:
            raw = llm_client(prompt)
            data = json.loads(raw)
            return {
                str(item.get("column")): item
                for item in data.get("columns", [])
                if item.get("column")
            }
        except Exception as e:  # noqa: BLE001 - LLM is best-effort
            logger.warning(f"llm annotation failed for {table_name}: {e}")
            return {}
