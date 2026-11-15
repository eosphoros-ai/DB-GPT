---
title: Contracts and gates
---

# Contracts and gates

An agent stage needs an output another stage can use and a clear way to judge whether it is adequate.

## Write a deliverable contract

For a fetching agent:

```text
Use only the configured database. Read the recorded metric version,
execute bounded read-only SQL, and explain missing evidence.
Output: metric ID/version; executed SQL; columns and units; result totals;
row/truncation limits; source artifacts; unresolved assumptions.
```

Keep the contract short and specific. Include evidence and unresolved items, not just the expected conclusion. Downstream agents receive upstream outputs within a context budget; oversized raw results can crowd out the important details.

## Choose the check

| Check | What it establishes | Limit |
| --- | --- | --- |
| Prompt output requirement | A requested structure and completion criterion | Model compliance is not automatic validation. |
| Review agent | A separate comparison or recomputation | It can repeat the same mistake; require independent evidence. |
| Deterministic tool/check | A specific tested property | Covers only its implemented checks. |
| Human stage gate | A person's decision about continuing | Does not validate every number or authorize every tool call. |

Do not call a prompt requirement a “validated artifact” unless a check actually ran and its result is available.

## Place a human gate

Use `human_confirm` after the stage that supplies decision material. Configure a message explaining the proposed scope and the consequences of continuing. Approval passes upstream content onward. Rejection or timeout stops the stage and blocks dependent work.

Use gates for a reporting scope, a costly investigation, or inclusion of remediation proposals. For a single high-risk tool operation, use [tool approval](../application/high_risk_tool_approval.md).

## Plan for exceptions

Say what a node should return when definitions, sources, or tools are missing. A structured “cannot proceed” result is easier to review than an invented answer. Inspect the actual failure before fixing resources or publishing a revised Flow; current documentation does not promise automatic resume from a successful checkpoint.
