---
title: Semantic Center quickstart
---

# Prepare definitions for your first query

Use a database connection that already works in **Datasources**. Prepare definitions with a domain owner who can confirm what the numbers mean.

## 1. Register and synchronize

Open **Semantic Layer**. Use the registration action to backfill existing connections into data spaces. Inspect the synchronization result, including failed connections. Open your space and synchronize metadata after a schema change.

![Data space registration and synchronization](/img/data-agent/en/semantic-spaces.png)

Check that the expected tables and fields appear. A successful connection is not the same as a complete or current metadata snapshot.

## 2. Activate with deliberate sampling

Use the space's activation action. Review the sampling limit and whether to generate drafts. Sampling reads data values; choose a limit appropriate for your data sensitivity and workload. The embedding-model option does not mean the semantic read tools use vector search.

Activation is a space lifecycle operation. It does not turn every draft into a published definition, and it does not establish database row-level permissions.

## 3. Review business meanings

Generate drafts if needed, then review them in the business-meaning view. Confirm or reject proposed definitions. Check field targets and synonyms, especially ambiguous terms such as “date,” “source,” and “valid order.”

Generated descriptions are proposals. Ask the business owner to verify the calculation scope rather than approving solely because the prose looks plausible.

## 4. Review and publish a metric

Open **Metrics** and inspect the metric definition. Record the formula, units, grain, time field, eligibility filters, deduplication, and dependencies where the definition needs them. Publish only after review.

The current UI provides inspection and publication, not a full metric-authoring editor.
Generated `COUNT(*)` drafts are starting points, not ready-made business metrics.
For a custom definition, use the preparation API below or your deployment's maintained
semantic setup process before publishing.

![Metrics and publication status](/img/data-agent/en/semantic-metrics.png)

Publishing creates a versioned snapshot. Agent reads use that snapshot, not the mutable draft body. After a change, publish a new version and check the returned version reference.

## 5. Use it from chat

Select **Smart Data Query** or **Smart Data Analysis**, attach the matching database, and ask the agent to retrieve the published metric and cite its version before querying. Follow [Using semantics with a Data Agent](./using-with-data-agent.md).

If no metric is returned, check the database, publication state, name/alias, and exact version. See [Troubleshooting](./troubleshooting.md).

## Prepare a custom metric through the API

For operators and integrators, the current preparation endpoints are:

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/semantic/spaces` | Find the space ID for your connection |
| `GET /api/v1/semantic/spaces/{ds_id}/tables` | Find synchronized table IDs for definition targets |
| `POST /api/v1/semantic/spaces/{ds_id}/entries` | Create a business-definition draft |
| `POST /api/v1/semantic/entries/{entry_id}/review` | Confirm, modify, or reject a definition |
| `POST /api/v1/semantic/spaces/{ds_id}/metrics` | Create a metric draft |
| `POST /api/v1/semantic/metrics/{metric_id}/publish` | Publish its snapshot |
| `GET /api/v1/semantic/spaces/{ds_id}/metrics/{metric_id}/versions/{version}` | Inspect an exact published snapshot |

For a table definition, replace `123` with the synchronized `orders` table ID
returned by the table-list endpoint, then POST this body to the entries endpoint:

```json
{
  "entry_type": "table",
  "target_id": 123,
  "entry_name": "orders",
  "entry_comment": "Order records; real and test orders coexist.",
  "synonyms": ["order records"],
  "entry_definition": "For eligible orders, require tenant_id=1, is_test=0, is_deleted=0, and status IN ('PAID','COMPLETED')."
}
```

Creation returns the entry ID. After business review, POST `{"action":"confirm"}`
to its review endpoint. Use `{"action":"reject"}` for an incorrect proposal.
The `modify` action accepts `updates` containing `entry_comment`, `synonyms`, or
`entry_definition` and returns the entry to draft status; review it again before confirming.

Example metric-creation body for the same database:

```json
{
  "metric_name": "eligible_order_count",
  "metric_type": "atomic",
  "metric_comment": "Number of tenant 1's real paid or completed orders.",
  "formula": "COUNT(*)",
  "metric_definition": "Count orders once by order_id. Use tenant_id=1, is_test=0, is_deleted=0, status IN ('PAID','COMPLETED'). Attribute by orders.created_at. Apply the requested half-open time interval. Unit: orders.",
  "dimensions": ["orders.channel_id"],
  "base_metrics": []
}
```

Adapt and review this body against your actual schema. Creation returns the metric ID;
POST `{"change_note":"Initial business-reviewed definition"}` to its publication
endpoint and record the returned version. Inspect that exact snapshot before using
it in a query. Read responses
use DB-GPT's standard result envelope. Follow your deployment's authentication setup.
These examples document requests; they do not create resources automatically.

The public routes above do not include a general metric update endpoint. Do not assume
the UI can edit an existing metric body or manage every historical version. Coordinate
definition changes through the maintained setup process and preserve existing citations.
