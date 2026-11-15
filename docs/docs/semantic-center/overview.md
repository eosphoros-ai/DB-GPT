---
title: Semantic Center
---

# Semantic Center

Semantic Center connects physical database structure to business meaning. It gives teams a place to review definitions and publish metric versions that data agents can read and cite.

For example, “January net receipts” needs more than a `SUM`: does it include freight, which orders qualify, and does a February refund affect January? Defining these choices once reduces repeated interpretation across queries and reports.

![Registered semantic data spaces](/img/data-agent/en/semantic-spaces.png)

## What you manage

| Object | Purpose |
| --- | --- |
| Data space | Semantic records associated with a registered database connection |
| Metadata | Synchronized table/column names, types, comments, keys, and maintained labels |
| Business meaning | Reviewed table/field definitions and synonyms |
| Metric | A named calculation with its business scope and definition |
| Published metric version | A snapshot that can be read by exact version and cited |
| Examples, relationships, guardrails | Maintained supporting context; runtime consumption varies |

The database remains the source of physical records. Semantic Center records business interpretation. A knowledge base stores documents for retrieval; it does not replace a published metric definition. A plugin supplies task methods; it does not own the definition.

## What agents currently read

Database-bound read tools expose metadata, published business meanings, published metric search, and exact metric versions. Search uses keywords and stored synonyms. Draft metrics are excluded, and a missing requested version does not silently fall back to another version.

The UI also exposes examples, relationships, and guardrails. Their presence is not evidence of automatic consumption or enforcement by the current semantic tools. Metadata is a snapshot, so resynchronize after database changes.

Next: [Quickstart](./quickstart.md) · [Metric governance](./metrics-and-governance.md).
