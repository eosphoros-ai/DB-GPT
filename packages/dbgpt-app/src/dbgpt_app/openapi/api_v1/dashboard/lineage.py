"""Derive display-only table and column lineage from validated widget SQL."""

from typing import Iterable, Optional

import sqlglot
from sqlglot import exp

from .schemas import (
    DashboardSchemaV1,
    DashboardWidget,
    QueryLineage,
    QueryLineageSource,
)


def extract_query_lineage(
    sql: str, data_source_id: str, *, dialect: Optional[str] = None
) -> QueryLineageSource:
    """Return stable source names without treating lineage as executable policy.

    SQL authorization and execution still use the security layer.  This function
    only derives human-readable metadata after parsing the same statement shape.
    """

    statement = sqlglot.parse_one(sql, read=dialect)
    cte_names = {
        cte.alias_or_name.casefold()
        for cte in statement.find_all(exp.CTE)
        if cte.alias_or_name
    }
    tables = {
        table.name
        for table in statement.find_all(exp.Table)
        if table.name and table.name.casefold() not in cte_names
    }
    columns = {
        column.sql(dialect=dialect)
        for column in statement.find_all(exp.Column)
        if column.name and column.name != "*"
    }
    return QueryLineageSource(
        data_source_id=data_source_id,
        tables=sorted(tables, key=str.casefold),
        columns=sorted(columns, key=str.casefold),
    )


def widget_lineage(widget: DashboardWidget) -> QueryLineage:
    sources = []
    if widget.query.federation is None:
        if widget.query.sql:
            sources.append(
                extract_query_lineage(
                    widget.query.sql,
                    widget.query.data_source_id,
                )
            )
    else:
        for source in widget.query.federation.sources:
            sources.append(extract_query_lineage(source.sql, source.data_source_id))
    return QueryLineage(sources=sources)


def enrich_schema_lineage(
    schema: DashboardSchemaV1,
    *,
    widgets: Optional[Iterable[DashboardWidget]] = None,
) -> DashboardSchemaV1:
    """Replace model-supplied lineage with AST-derived metadata in place."""

    for widget in widgets or schema.widgets:
        try:
            widget.query.lineage = widget_lineage(widget)
        except Exception:
            # Validation reports malformed SQL through the authoritative query
            # security path.  A draft with a server-created widget error may still
            # be saved, so lineage extraction remains best effort for that widget.
            widget.query.lineage = QueryLineage()
    return schema
