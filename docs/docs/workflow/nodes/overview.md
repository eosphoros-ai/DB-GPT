# Node Kinds and the Orchestration Contract

A workflow DAG is built from a small set of node kinds. Intelligence lives in `agent` nodes;
everything else is boundary, data-plane or gate.

## Kind reference

| Kind | Role | Notes |
|---|---|---|
| `start` | Boundary | Entry point; broadcasts the user's question to all nodes. |
| `output` | Boundary | Single DAG leaf; the last node's output becomes the run's final answer. |
| `agent` | Intelligence | An isolated ReAct agent: goal + tool boundary + output contract. The workhorse — see [agent node](./agent.md). |
| `file_data` | Data plane | Deterministic CSV/Excel load with row cap and summary. Kept as an operator on purpose: upload resolution and truncation protection are safer outside an agent. |
| `human_confirm` | Gate | Pauses the run, floats a confirmation dock above the composer; resumes on approve, fails on reject/timeout. See [confirmation gates](./human-confirm.md). |

### Retired kinds

Earlier generations shipped hard-coded operator kinds. They are gone from the palette and from
built-in templates; existing flows still compile for compatibility but new work should use agents:

| Retired kind | Replaced by |
|---|---|
| `db_query` | `agent` node with `sql_query` tool (grounding contract replaces blind extraction) |
| `ai_analysis` | `agent` node with an analysis goal |
| `visualize` | charts live inside the report node's HTML artifact |
| `report` (operator) | `agent` node with the report contract (`html_interpreter` only) |

## The data channel

Every node's user message contains, in execution order:

```
<goal from config>

User question: <the end user's original message>

Upstream node outputs (in execution order):
<source node="Schema & Semantic Grounding" kind="agent">
…that node's clean final output…
</source>
<source node="Pivot Analysis" kind="agent">
…
</source>
```

Two consequences worth internalizing:

1. **Ancestor outputs, not just the immediate parent's.** A review node three hops downstream
   can receive the grounding card. Independent parallel branches do not receive each other's
   findings. Context budget caps the total (~20k chars), oldest blocks truncate first.
2. **Outputs are contracts.** UI protocol (step markers, artifact fences) is stripped before the
   text reaches the next agent — what flows forward is exactly what the node answered.

## Writing output contracts

End every goal with an explicit `Output:` line naming the deliverable's shape, e.g.:

> `Output: semantic card (tables / columns / calibers / dialect) plus a volume overview.`

Downstream goals then say *based on the upstream semantic card…* — the contract is the interface.
Nodes without a contract tend to answer in prose that the next agent must guess at.

## Control vs data

Edges define dependencies and therefore which stages are ancestors of a node.
With a star-shaped DAG, sibling agents share the original question and common ancestor outputs;
they do not receive each other's results. Connect branches to a common downstream stage to
combine their results. For parallel execution, use the supported `parallel_group` structure.

Next: [agent node](./agent.md) · [data entry](./data-entry.md) · [confirmation gates](./human-confirm.md)
