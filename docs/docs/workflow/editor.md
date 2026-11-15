# The Flow Editor

The editor is where templates become your flows: a node canvas on the left, a property panel on
the right, and deploy controls in the header.

![Editor canvas with a DB analysis flow](/img/data-agent/en/workflow-editor.png)

## Canvas basics

- **Add node** — pick a kind from the palette; intelligence nodes are `agent` nodes, plus the
  `start` / `output` boundaries, the `file_data` data-plane entry and `human_confirm` gates.
- **Connect** — drag from a node's output handle to another node's input handle. Edges declare the
  dependencies; each task receives outputs from its ancestor nodes within the context budget.
- **Delete / relabel** — select a node and use the property panel or the delete key.

## Property panel

Click a node to edit it. For an agent node the panel exposes the full capability boundary:

![Agent node property panel](/img/data-agent/en/workflow-agent.png)

| Field | Meaning |
|---|---|
| Label | Node name shown on the run card chain. |
| Agent profile | Persona skeleton: data analyst / knowledge expert / general executor. |
| Goal | The node's objective. End it with an `Output:` contract line — downstream nodes rely on it. |
| Tools | Checkbox boundary: SQL, code interpreter, knowledge retrieve, HTML render, shell. |
| Skills | Skill packages mounted into the node (adds `load_skill` / script tools). |
| Datasources | Which connectors `sql_query` may touch. Empty = no SQL tool at all. |
| Knowledge | Knowledge spaces backing `knowledge_retrieve` and the `kb_*` family. |
| MCP | Inline `sse:` / `http:` MCP servers scoped to this node. |
| Max turns | ReAct loop cap for this node (1–30); budget each stage for its scope. |
| Parallel group | A shared group for independent agent branches with a common upstream and a downstream join. |

See [agent node reference](./nodes/agent.md) for writing goals that compose well.

Parallel branches receive their common ancestors' outputs, not each other's findings.
Connect both branches to a review stage when it needs to inspect both results.

## Validate, save, deploy

- **Save** writes the flow in `developing` state — a draft. Drafts do **not** run from chat.
- **Publish** deploys the DSL as an AWEL DAG, registers it and flips the flow to `running`.
  Only `running` flows are runnable and survive server restarts.
- The header shows the state badge; the template center and My Flows list show it too.

:::tip
After a server restart, `running` flows re-register automatically. A flow stuck in `developing`
after a restart is not a bug — deploy it once.
:::

## Instances and versions

Running a built-in template from chat instantiates it into My Flows on first use (cached per
browser). Editing your instance never touches the template; bumping the template's creation
parameters invalidates old caches so users pick up the new shape on next use.

Next: [Node reference](./nodes/overview.md) · [Custom operators](./custom-operator.md)

## Start with responsibility, then configure

Write the stage's business responsibility before selecting tools. Specify the input assumptions,
required evidence, output structure, and what to return when the work cannot proceed.
An `Output:` instruction is a prompt contract; use a review stage or explicit check when
correctness matters. See [Contracts and gates](./contracts-and-gates.md).
