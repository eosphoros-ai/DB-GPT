---
title: Controlled execution
---

# Controlled execution

Controls operate at different layers. Choose the layers your task needs and inspect the effective configuration instead of relying on the scenario name.

| Layer | What to configure or inspect | Practical boundary |
| --- | --- | --- |
| Database | Account privileges and selected connection | Prefer a read-only account; semantic labels do not grant or revoke SQL privileges. |
| Agent tools | Mounted tools and node resource configuration | A plugin manifest is not proof that every declared control is enforced. |
| Tool approval | Effective policy and pending tool request | Approval covers the proposed call, not the correctness of its output. |
| Execution environment | Code/shell environment, accessible files, network configuration | Isolation depends on the deployed environment; not every tool runs in a sandbox. |
| Flow | Node responsibilities, dependencies, review and human gates | A stage gate is distinct from approval for a single tool call. |
| Delivery | Tool traces, artifact status, truncation, citations | A generated summary alone is insufficient evidence of execution. |

See [High-risk tool approval](../application/high_risk_tool_approval.md) for policy behavior, [Sandbox](../sandbox/index.md) for execution setup, and [Harness](../harness/usage.md) for engine configuration.

## Before running

Specify the database or document scope, permitted actions, time window, output limits, and whether changes are allowed. SQL optimization and metadata expert scenarios normally produce read-only diagnoses and proposals. Review proposed DDL through your own change process; an index candidate is not an applied index.

## During and after running

Read a confirmation request before approving it. Check failures and retries in the trace. Verify that links point to completed artifacts and that large results have explicit limits. If the provider fails, restore authentication or quota and rerun; an error message is not a completed analysis.

Rules maintained in Semantic Center can express intended boundaries. The current semantic read tools do not provide automatic row-level permission enforcement, a cost-based approval engine, or universal SQL caliber validation.
