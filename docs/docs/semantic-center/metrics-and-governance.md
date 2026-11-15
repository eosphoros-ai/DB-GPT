---
title: Metrics and governance
---

# Metrics and governance

A metric definition is an agreement about calculation, not just a label. Make the agreement specific enough that another person can reproduce it.

## Review checklist

| Choice | Questions to resolve |
| --- | --- |
| Formula and units | Gross or net? Freight included? Currency or thousands of currency units? |
| Grain | Per order, payment event, refund event, customer, or day? |
| Eligibility | Which tenant, statuses, real/test orders, and canceled records qualify? |
| Time | Order date, payment date, or refund date? Which timezone and interval boundaries? |
| Joins and deduplication | Can multiple item/payment/refund rows multiply each other? |
| Dependencies | Which fields, dimensions, and base metrics does the formula require? |
| Evidence | Who confirmed the meaning, and which version was used? |

These properties are usable only when present in the saved definition. Semantic tools do not invent missing filters or time fields.

## Drafts and published versions

Drafts are proposals. The current UI supports inspection and publication; custom authoring
and changes require the maintained setup process described in [Quickstart](./quickstart.md).
Publishing records a snapshot. Search and metric retrieval expose published snapshots;
they do not fall back to draft contents. Ask the agent to reuse the returned integer
version throughout a multi-step analysis.

If version 2 is required and absent, stop and resolve the missing definition. Replacing it with the latest version changes the question.

![Metric status and definition management](/img/data-agent/en/semantic-metrics.png)

## Example: payment and refund events

In the synthetic commerce example, payment-month and refund-month attribution are separate decisions. An order can be placed in December, paid in January, and refunded in February. GMV and net receipts can therefore legitimately differ for January.

Likewise, joining two item rows, two payment rows, and two refund rows can yield eight rows. Aggregate each event source at the intended grain before combining it; verify against the published definition rather than memorizing one SQL pattern.

## Change a definition safely

Review the changed formula and affected dependencies, publish a new version, rerun representative queries, and compare results with the earlier version. Keep the version citation with the report. Current tools do not automatically pin versions across sessions or prove that all downstream SQL conforms to the definition.
