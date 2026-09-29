# Dashboard Schema 1.1: constrained federation

Schema 1.1 is an optional, backward-compatible extension of Schema 1.0. Existing
single-source dashboards remain valid. A widget that uses `query.federation` must
set the top-level `schema_version` to `1.1` and must not also set top-level SQL.

## Why this is not arbitrary cross-database SQL

DB-GPT does not forward one statement to several databases. Each source has its own
connector, authorization decision, read-only SQL parse, table/column allowlist,
parameter binding, timeout, and row limit. Only the small validated result sets enter
an application-side `union_all`, `inner` join, or `left` join.

Hard limits:

- two to four source queries;
- at most 2,000 rows per source;
- at most 5,000 output rows;
- at most 60 seconds per source query;
- equality joins only, with exactly two sources;
- no cartesian join, arbitrary expression, DDL/DML, or anonymous execution.

## Union example

```json
{
  "data_source_id": "north-sales",
  "sql": null,
  "federation": {
    "mode": "union_all",
    "sources": [
      {
        "alias": "north",
        "data_source_id": "north-sales",
        "sql": "SELECT month, amount FROM sales WHERE month >= :start_month",
        "default_parameters": {"start_month": "2026-01"},
        "filter_parameters": {},
        "column_mapping": {"month": "month", "amount": "sales"},
        "timeout_seconds": 30,
        "max_rows": 1000
      },
      {
        "alias": "south",
        "data_source_id": "south-sales",
        "sql": "SELECT month, amount FROM sales WHERE month >= :start_month",
        "default_parameters": {"start_month": "2026-01"},
        "filter_parameters": {},
        "column_mapping": {"month": "month", "amount": "sales"},
        "timeout_seconds": 30,
        "max_rows": 1000
      }
    ],
    "max_output_rows": 2000
  },
  "filter_parameters": {},
  "default_parameters": {},
  "output_fields": [
    {"name": "month", "type": "string"},
    {"name": "sales", "type": "number"}
  ]
}
```

`column_mapping` maps each physical result column to the public output name used by
the chart. Every union source must map exactly the declared widget outputs.

## Join example

For a join, `sources` contains exactly two entries and adds:

```json
{
  "mode": "join",
  "join": {
    "left_alias": "actual",
    "right_alias": "plan",
    "left_field": "store",
    "right_field": "store",
    "join_type": "left"
  }
}
```

Join fields refer to mapped output names, not raw database column names. Duplicate
non-key output names are rejected. A left join represents missing right-side values
as `null`; an inner join omits unmatched rows.

## Authorization and failure behavior

The actor must have dashboard query permission and data-source permission for every
declared source. One denied source denies the whole federated widget. One invalid or
failed source returns a widget-level error; other widgets in the dashboard can still
refresh. Published public pages contain only the resulting immutable snapshot and
never re-run federation queries.
