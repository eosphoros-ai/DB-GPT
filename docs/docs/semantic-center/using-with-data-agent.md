---
title: Using semantics with a Data Agent
---

# Using semantics with a Data Agent

Select the database that owns the semantic space. Smart Data Query and Smart Data Analysis mount semantic read tools when the database connection loads successfully; a separate knowledge-base attachment is not required for these reads.

## Ask for an explicit evidence chain

```text
Query January 2026 net receipts by acquisition source.
First retrieve the published net receipts definition and its version.
Read the business meanings of receipt date and acquisition source.
Check the physical columns, follow the recorded payment/refund date rules,
and avoid multiplying amounts across item, payment, and refund joins.
Return executed SQL, CNY totals, the metric citation, and missing definitions.
```

With `Semantic_Commerce_Case`, select **Semantic Center: net receipts** on the homepage. This is a synthetic commerce demonstration; use your own governed metric for real work.

![Smart Data Query recommended questions](/img/data-agent/en/query-entry.png)

## Understand the tool sequence

| Tool | Read result |
| --- | --- |
| `semantic_search_metrics` | Published candidates matching a keyword or saved alias |
| `semantic_get_metric` | Complete published snapshot by metric ID/name and optional exact version |
| `semantic_search_business` | Published table/column meanings and synonyms |
| `semantic_get_metadata` | Table/column snapshot and maintained metadata labels |

Search each meaningful business noun separately when a long question gives no match. Results include source/space information and may be truncated; narrow the keyword or table scope. The tools are bound to the selected connection and cannot be redirected by a model parameter to another database.

## Verify the result

Compare the cited snapshot with SQL: units, time predicates, filters, and aggregation grain. Check the actual execution record and result size. A metric citation identifies a definition source; it does not certify that the SQL implemented every rule.

If the answer discusses lineage, distinguish saved metric dependencies, declared foreign keys, and inferred relationships. These four tools do not provide general scheduler or end-to-end lineage discovery.
