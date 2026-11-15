---
title: Agentic Workflow quickstart
---

# Run your first Agentic Workflow

Start with a template, understand its stages, and bind a working database before running.

## 1. Choose a template

Open **Workflow → Built-in Templates**. **DB Data Fetch** is a small first task; **DB Intelligent Analysis** separates grounding, planning, parallel analysis/data-quality checks, numeric review, and reporting.

![Template center](/img/data-agent/en/workflow-templates.png)

Click **Edit a Copy** to inspect and customize the template. Your changes do not modify the shipped template.

## 2. Configure responsibilities and resources

Select the workflow database in the editor and inspect each agent node's datasources and tools. Give each stage a clear deliverable. The database attachment in the main composer is not a substitute for the Flow's node resource configuration.

![Analysis template stages in the editor](/img/data-agent/en/workflow-editor.png)

For a sales analysis, specify the reporting period, currency, date encoding, grouping dimensions, and how a reviewer should check totals. The `Walmart_Sales` example is a demo dataset, not live operating data.

## 3. Save and publish

**Save** retains a draft. **Publish** deploys the Flow for chat execution. Verify its runnable state after publication. A saved but undeployed Flow can fail with “dag id not found.”

## 4. Run with a bounded question

Use **Run** from the Flow list or choose a Flow from the composer context menu.

```text
Analyze sales by store and month in the configured demo database.
Check the date format before grouping, reconcile the totals independently,
and produce a report with SQL evidence, units, and data-quality limitations.
```

The run view displays stage progress. Open the active node to inspect its tools; review the report artifact after completion.

## 5. Add a gate when a decision matters

For a custom Flow, add `human_confirm` after planning when a person must approve the scope before expensive analysis. This is a deliberate pause, not a required node in every template.

Next: [Editor](./editor.md) · [Contracts and gates](./contracts-and-gates.md).
