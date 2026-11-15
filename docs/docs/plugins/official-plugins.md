---
title: Official plugins
---

# Official plugins

These are the five official homepage scenarios. Availability depends on enablement and required resources.

| Plugin | Provide | Typical delivery | First task |
| --- | --- | --- | --- |
| Smart Data Query | Database; published definitions when metric-specific | SQL, result table, available metric citations | Net receipts by source |
| Smart Data Analysis | Database or suitable files; period and objectives | Analysis, report, dashboard | Walmart sales dashboard |
| SQL Optimization Expert | Database, original SQL, parameters and symptoms | Evidence-based diagnosis, rewrite/index candidates, validation plan | Diagnose this SQL |
| Metadata and Architecture Expert | Database and table scope | Dictionary, physical ER, schema report | Data dictionary for selected tables |
| Financial Report Analysis | Financial-report files and periods | Source-based financial analysis and report | Analyze an uploaded annual report |

## Smart Data Query

Start with a bounded question. Ask for published metric definitions before calculation and inspect time/filter/join choices. The commerce recommendations cover net receipts, freight, join fanout, and cross-month attribution using synthetic data.

## Smart Data Analysis

State the decisions the report should support. For a dashboard, review the plan before generation and open the widgets afterwards. SQL execution alone does not validate calendar ordering, non-null time axes, or units.

## SQL Optimization Expert

Supply the actual SQL and engine. Separate measured performance, plan estimates, and static hypotheses. Default diagnoses do not apply DDL or run `EXPLAIN ANALYZE`; candidate indexes and rewrites need semantic and workload validation.

## Metadata and Architecture Expert

Choose the object scope. Catalog results establish physical facts; missing comments stay unknown. A physical ER should distinguish declared foreign keys from inferred associations. Inferred associations must not become real constraints or DBML foreign keys.

## Financial Report Analysis

Provide traceable files, reporting periods, currency, and units. Check document citations and comparable accounting scope. An incomplete upload or missing source is a reason to narrow the task, not invent a figure.

See [Showcases](../use_cases.mdx) for homepage entry screenshots and reproducible task recipes.
