# Confirmation Gates (`human_confirm`)

A `human_confirm` node pauses the run and asks a human to decide before the chain continues.
It is the workflow-level counterpart of the tool approval dock: use it where a *stage* decision
matters (scope, window, whether to include a remediation package), not for individual tool calls.

## Configuration

| Field | Meaning |
|---|---|
| `message` | The question shown in the confirmation dock. Summarize what upstream produced and what continuing implies. |

## Runtime behavior

- When the node starts, the run card shows it as *waiting* and a dock floats above the composer
  with the message plus approve / reject actions.
- **Approve** — the node outputs the upstream content unchanged and the chain continues.
- **Reject or timeout** — the node fails; downstream nodes fail with it and the run card marks
  the gate red. Timeouts follow the approval policy TTL in Settings → Tool Approval.
- The decision is audited alongside tool approvals (who, when, which conversation).

## When to place a gate

- **Before expensive stages**: e.g. after grounding/plan, before a ten-minute analysis chain, let
  a human confirm the question list.
- **Before remediation packages**: ops-style flows produce change suggestions (index DDL,
  parameter changes). A gate lets the owner pick which suggestions enter the final report.
- **Not** for routine checks — every gate adds latency and confirmation fatigue; prefer tighter
  node contracts and read-only tool boundaries first.

## Example placement

```text
start → health patrol → root cause → remediation suggestions
      → human_confirm("Include which suggestions in the report?")
      → patrol report → output
```

The gate's message should carry the decision material: reference the upstream anomaly list and
note that rejecting stops the run.

Next: [runs & artifacts](../runs-and-artifacts.md) · [troubleshooting](../troubleshooting.md)
