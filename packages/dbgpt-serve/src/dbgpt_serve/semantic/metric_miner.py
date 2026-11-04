"""L3 metric candidate mining (S3, phase 3).

Mines ``sem_metric`` drafts from L1 facts plus an optional LLM:

- heuristic mode: numeric amount-like columns -> SUM candidates;
  every active table -> COUNT(*) candidate; ratio/率 columns skipped (P1).
- llm mode: one JSON proposal list per table (name/comment/formula/dims).

Candidates are created as drafts (version=0); the caliber version row is
snapshot only at publish time (see :meth:`SemanticService.publish_metric`).
Dedup by (ds_id, metric_name) keeps mining idempotent.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from dbgpt_serve.semantic.models import (
    SemColumnDao,
    SemMetricDao,
    SemMetricEntity,
    SemTableDao,
    dump_json,
)

logger = logging.getLogger(__name__)

AMOUNT_HINTS = ("amount", "amt", "gmv", "price", "fee", "cost", "revenue")
DIM_HINTS = ("region", "channel", "city", "category", "dt", "date", "status")
NUM_TYPES = ("int", "decimal", "numeric", "float", "double", "bigint")

LLM_METRIC_PROMPT = """你是指标口径矿工。给定表 {table} 的列清单（含类型/注释），
提出 1-5 个业务指标候选（原子指标优先），含名称/业务说明/SQL 表达式/维度。
只输出 JSON：
{{"metrics":[{{"name":...,"comment":...,"formula":...,"dimensions":[...]}}]}}
列清单：{columns}"""


class MetricMiner:
    """Mine L3 metric drafts for one semantic space (idempotent)."""

    def __init__(
        self,
        table_dao: Optional[SemTableDao] = None,
        column_dao: Optional[SemColumnDao] = None,
        metric_dao: Optional[SemMetricDao] = None,
    ) -> None:
        self._table_dao = table_dao or SemTableDao()
        self._column_dao = column_dao or SemColumnDao()
        self._metric_dao = metric_dao or SemMetricDao()

    def mine(
        self,
        ds_id: int,
        llm_client: Optional[Callable[[str], str]] = None,
    ) -> Dict[str, int]:
        existing = {m.metric_name for m in self._metric_dao.list_by_ds(ds_id)}
        counts = {"metrics": 0, "skipped": 0}
        session = self._metric_dao.get_raw_session()
        session.expire_on_commit = False
        try:
            for table in self._table_dao.list_by_ds(ds_id, status="active"):
                columns = self._column_dao.list_by_table(ds_id, table.id, "active")
                dims = [
                    c.column_name
                    for c in columns
                    if any(h in (c.column_name or "").lower() for h in DIM_HINTS)
                ]
                proposals = self._llm_metrics(llm_client, table.table_name, columns)
                if not proposals:
                    proposals = self._heuristic_metrics(table.table_name, columns)
                for prop in proposals:
                    name = str(prop.get("name") or "").strip()
                    if not name or name in existing:
                        counts["skipped"] += 1
                        continue
                    session.add(
                        SemMetricEntity(
                            ds_id=ds_id,
                            metric_name=name,
                            metric_comment=prop.get("comment"),
                            metric_type="atomic",
                            formula=prop.get("formula"),
                            dimensions=dump_json(prop.get("dimensions") or dims),
                            status="draft",
                            version=0,
                            provenance=prop.get("provenance", "mined"),
                        )
                    )
                    existing.add(name)
                    counts["metrics"] += 1
            session.commit()
        finally:
            session.close()
        return counts

    @staticmethod
    def _heuristic_metrics(table_name: str, columns: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = [
            {
                "name": f"cnt_{table_name}",
                "comment": f"{table_name} 表行数计数",
                "formula": "COUNT(*)",
                "provenance": "mined",
            }
        ]
        for col in columns:
            low = (col.column_name or "").lower()
            ctype = (col.column_type or "").lower()
            if any(h in low for h in AMOUNT_HINTS) and any(
                t in ctype for t in NUM_TYPES
            ):
                out.append(
                    {
                        "name": f"sum_{table_name}_{low}",
                        "comment": col.column_comment
                        or f"{table_name}.{col.column_name} 求和（口径待业务确认）",
                        "formula": f"SUM({col.column_name})",
                        "provenance": "mined",
                    }
                )
        return out

    @staticmethod
    def _llm_metrics(
        llm_client: Optional[Callable[[str], str]],
        table_name: str,
        columns: List[Any],
    ) -> List[Dict[str, Any]]:
        if not llm_client or not columns:
            return []
        payload = [
            {
                "column": c.column_name,
                "type": c.column_type,
                "comment": c.column_comment,
            }
            for c in columns
        ]
        prompt = LLM_METRIC_PROMPT.format(
            table=table_name, columns=json.dumps(payload, ensure_ascii=False)
        )
        try:
            data = json.loads(llm_client(prompt))
            props = data.get("metrics", [])
            for prop in props:
                prop["provenance"] = "llm_draft"
            return props
        except Exception as e:  # noqa: BLE001 - LLM is best-effort
            logger.warning(f"llm metric mining failed for {table_name}: {e}")
            return []
