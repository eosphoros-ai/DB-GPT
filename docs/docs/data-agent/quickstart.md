---
title: Your first data task
---

# Your first data task

This guide starts with a running DB-GPT installation. Complete the [installation guide](../getting-started/index.md) and configure a model that supports the tools needed by your scenario before continuing.

## 1. Connect a database

Open **Datasources**, add a supported connection, and verify that its tables are accessible. Use a read-only database account for query and analysis tasks. Connecting a database does not automatically supply business metric definitions.

For a first experiment, use a small database whose contents you can independently check. The homepage commerce examples expect a separately prepared database named `Semantic_Commerce_Case`; its presence is not guaranteed by installing DB-GPT.

## 2. Prepare the business meaning

If your question involves a governed metric, open **Semantic Layer**, register the connection, synchronize metadata, review generated definitions, and publish the metric. Follow [Semantic Center quickstart](../semantic-center/quickstart.md).

If no published definition exists, ask the agent to identify the missing definition and clarify the scope before calculating. Do not silently treat a draft as an approved metric.

## 3. Choose a scenario

Open the homepage and select **Data Query**. Choose a recommended question or write your own. Attach the database using the composer database control; verify the selected model before sending.

![Homepage scenario selection](/img/data-agent/en/query-entry.png)

Try this question with your own table and metric names:

```text
For January 2026, calculate net receipts by acquisition source.
Read the published metric definition first and state its version.
Use the definition's payment/refund date rules and avoid join fanout.
Return the executed SQL, CNY amounts, source references, and any missing evidence.
```

The commerce examples contain synthetic data. Their figures do not describe a real business.

## 4. Check the answer

Open the query and tool details. Check the selected database, time predicates, eligibility filters, aggregation grain, units, metric version, and whether the result is truncated. Open an artifact before treating its link as a delivered file.

An answer that only contains a SQL draft is not evidence that SQL ran. A dashboard draft is not evidence that all widgets passed validation. A CSV must come from an executed result with a known export limit.

## 5. Expand the task

Choose **Data Analysis** for an investigation or dashboard. Use [Agentic Workflow](../workflow/quickstart.md) when you need repeatable stages and an independent review. Keep the first task small enough to check by hand.

Next: [Concepts](./concepts.md) · [Showcases](../use_cases.mdx).
