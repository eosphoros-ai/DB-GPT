# Data Entry Node (`file_data`)

The `file_data` node is the workflow's deterministic data plane: it resolves an uploaded
CSV/Excel file, loads it with a row cap and emits a compact summary (file id, row count, column
count) that downstream agent nodes receive through the data channel.

## Configuration

| Field | Meaning |
|---|---|
| `file_name` | Display name of the uploaded file. |
| `file_id` | Upload id resolving into the taskflow file cache. |
| `max_rows` | Row cap for the loaded frame (protects context and compute). |

## Why it is not an agent

Upload resolution, encoding sniffing and truncation protection are mechanical work where
determinism beats improvisation: an agent "loading" a file can hallucinate a path or silently
drop rows. Keeping the entry point as an operator means the summary downstream nodes cite is
exactly what was loaded. Agents then analyze via `code` / `sql_query` against the
resolved dataset instead of re-reading raw files.

## Databases instead of files

For database-backed workflows there is **no entry node**: `agent` nodes bind `datasources`
directly and the grounding node profiles the schema itself (table list, row counts, enum values,
join hints). See [agent node](./agent.md).

## Retired data operators

| Retired | Successor |
|---|---|
| `db_query` (blind extraction) | grounding `agent` node with `sql_query` + an explicit semantic-card contract |
| `visualize` (gpt-vis text dashboards) | charts embedded in the report node's HTML artifact |

Next: [node overview](./overview.md) · [agent node](./agent.md)
