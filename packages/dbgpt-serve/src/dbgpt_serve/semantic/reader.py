"""Read-only, connection-scoped access to authoritative semantic records."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .models import filters_to_dict
from .service import SemanticService


def _decode(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def _matches(query: str, row: Dict[str, Any], names: List[str]) -> bool:
    """Keyword lookup, including business aliases embedded in a question."""
    if not query.strip():
        return True
    text = json.dumps(row, ensure_ascii=False).casefold()
    terms = re.findall(r"\w+", query.casefold())
    aliases = []
    for key in names:
        value = _decode(row.get(key))
        aliases.extend(value if isinstance(value, list) else [value])
    return any(term in text for term in terms) or any(
        isinstance(alias, str)
        and len(alias.strip()) >= 2
        and alias.casefold() in query.casefold()
        for alias in aliases
    )


class SemanticReader:
    """A reader bound by the caller to its already-authorized DB connection.

    No operation accepts a replacement connection or semantic-space ID.
    Business annotations are published-only; metric formulas come exclusively
    from immutable published snapshots, never the mutable metric draft.
    """

    def __init__(self, conn_id: str, service: Optional[SemanticService] = None) -> None:
        self.conn_id = conn_id
        self.service = service or SemanticService()

    def _context(self) -> Dict[str, Any]:
        space = self.service._ds_dao.get_by_conn(self.conn_id)
        return {
            "source": "semantic_center",
            "conn_id": self.conn_id,
            "ds_id": space.id if space else None,
            "space_status": space.status if space else "not_found",
            "last_sync_at": (
                space.last_sync_at.isoformat() if space and space.last_sync_at else None
            ),
        }

    @staticmethod
    def _limit(limit: int) -> int:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        return limit

    def _result(
        self, context: Dict[str, Any], items: List[Dict[str, Any]], limit: int
    ) -> Dict[str, Any]:
        return {
            **context,
            "status": (
                "ok" if items else "empty" if context["ds_id"] else "space_not_found"
            ),
            "items": items[:limit],
            "matched_count": len(items),
            "truncated": len(items) > limit,
            "policy": "published_only",
            "message": (
                None
                if items
                else "No matching published definitions or active metadata. "
                "Do not infer an authoritative caliber from drafts or an empty result."
            ),
        }

    def metadata(
        self, table_name: str = "", query: str = "", limit: int = 20
    ) -> Dict[str, Any]:
        limit = self._limit(limit)
        context = self._context()
        tables = self.service.list_tables(context["ds_id"]) if context["ds_id"] else []
        items = []
        for table in tables:
            if table_name and table["table_name"] != table_name:
                continue
            columns = self.service.list_columns(context["ds_id"], table["id"])
            columns = [c for c in columns if c["status"] == "active"]
            for column in columns:
                column["enum_values"] = _decode(column.get("enum_values"))
            row = {**table, "columns": columns}
            if _matches(query, row, ["table_name", "table_comment"]):
                items.append(row)
        result = self._result(context, items, limit)
        result["policy"] = "active_metadata_snapshot"
        result["message"] = result["message"] or (
            "Metadata is a synced snapshot; whitelist and sensitivity flags "
            "are descriptive here, not execution enforcement."
        )
        return result

    def business_semantics(
        self, query: str = "", table_name: str = "", limit: int = 20
    ) -> Dict[str, Any]:
        limit = self._limit(limit)
        context = self._context()
        items = []
        if context["ds_id"]:
            tables = self.service.list_tables(context["ds_id"])
            targets = {}
            for table in tables:
                targets[("table", table["id"])] = (table["table_name"], None)
                for column in self.service.list_columns(context["ds_id"], table["id"]):
                    if column["status"] == "active":
                        targets[("column", column["id"])] = (
                            table["table_name"],
                            column["column_name"],
                        )
            for entry in self.service.list_entries(context["ds_id"], "published"):
                target = targets.get((entry["entry_type"], entry["target_id"]))
                if not target:
                    continue
                row = {
                    **entry,
                    "table_name": target[0],
                    "column_name": target[1],
                    "synonyms": _decode(entry.get("synonyms")),
                    "entry_definition": _decode(entry.get("entry_definition")),
                }
                if table_name and row["table_name"] != table_name:
                    continue
                if _matches(query, row, ["entry_name", "entry_comment", "synonyms"]):
                    items.append(row)
        return self._result(context, items, limit)

    def get_metric(
        self,
        metric_id: Optional[int] = None,
        metric_name: str = "",
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        context = self._context()
        if (metric_id is None) == (not metric_name):
            raise ValueError("Provide exactly one of metric_id or metric_name")
        if version is not None and version < 1:
            raise ValueError("version must be a positive integer")
        metric = None
        if context["ds_id"]:
            metric = (
                self.service._metric_dao.get(metric_id)
                if metric_id is not None
                else self.service._metric_dao.get_by_name(context["ds_id"], metric_name)
            )
        if not metric or metric.ds_id != context["ds_id"]:
            return {**context, "status": "not_found", "metric": None}
        if metric.status != "published" or not metric.publish_version:
            return {
                **context,
                "status": "not_published",
                "metric": None,
                "message": "Metric is not published; do not use its draft caliber.",
            }
        selected = version if version is not None else metric.publish_version
        snapshot = self.service._metric_version_dao.get_version(metric.id, selected)
        if not snapshot or not snapshot.published_at:
            return {**context, "status": "version_not_found", "metric": None}
        row = filters_to_dict(
            metric, ["id", "metric_name", "metric_comment", "metric_type", "provenance"]
        )
        row.update(
            filters_to_dict(
                snapshot,
                [
                    "version",
                    "metric_definition",
                    "formula",
                    "base_metrics",
                    "dimensions",
                ],
            )
        )
        for key in ("metric_definition", "base_metrics", "dimensions"):
            row[key] = _decode(row[key])
        row.update(
            {
                "status": "published",
                "latest_published_version": metric.publish_version,
                "published_at": snapshot.published_at.isoformat(),
                "published_by": snapshot.published_by,
                "citation": f"semantic::{self.conn_id}/metric/{metric.id}@v{selected}",
            }
        )
        return {**context, "status": "ok", "metric": row}

    def search_metrics(self, query: str = "", limit: int = 10) -> Dict[str, Any]:
        limit = self._limit(limit)
        context = self._context()
        items = []
        if context["ds_id"]:
            for metric in self.service.list_metrics(context["ds_id"], "published"):
                result = self.get_metric(metric_id=metric["id"])
                row = result["metric"]
                if row and _matches(query, row, ["metric_name", "metric_comment"]):
                    items.append(row)
        return self._result(context, items, limit)
