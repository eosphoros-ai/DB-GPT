# The Agent Node

The `agent` node runs one focused ReAct agent inside the workflow. It is isolated by design:
fresh memory, its own conversation id, no visibility into the main chat or into other nodes'
tool traces — only the goal you give it, the user's question, and upstream outputs.

## Configuration reference

| Field | Type | Effect |
|---|---|---|
| `agent_profile` | `react_data` / `react_knowledge` / `react_general` | Persona skeleton + default tool affinity (analyst / knowledge expert / careful executor). |
| `goal` | text | The node's objective. **End with an `Output:` contract line.** |
| `tools` | list | Capability boundary. Unselected tools simply do not exist for this node. |
| `skills` | list | Skill packages; mounts `load_skill` / `execute_skill_script_file` and lists skills in the prompt. |
| `datasources` | list | Connectors `sql_query` may touch. One datasource binds directly; several switch `sql_query` to explicit-`db_name` mode. Empty = no SQL tool. |
| `knowledge` | list | Knowledge spaces behind `knowledge_retrieve` + the `kb_ls/kb_glob/kb_grep/kb_cat/semantic_search` family. |
| `mcp` | list | Inline MCP specs (`sse:<url>` / `http:<url>`); failing servers are skipped, not fatal. |
| `max_turns` | 1–30 | ReAct loop cap for this node. |
| `model` | text | Override the chat model for this node (default: session model). |

Available tool ids: `sql_query`, `code`, `knowledge_retrieve`, `html_interpreter`,
`bash`, `web_search`, `web_fetch`.

## Writing goals that compose

A good goal has three parts: **role stance**, **behavior constraints**, **output contract**.

```text
Map business nouns in the user's question to tables/columns/calibers: query metadata
and bounded samples with sql_query (schema, distinct/limit samples; no full scans);
when multiple calibers exist, list candidates and state the default choice with
reasoning. Output a query plan: per-step SQL draft plus expected columns and row caps.
        └──────────────────────────────┬──────────────────────────────────────┘
                                  output contract
```

Patterns that pay off across the built-in templates:

- **Ground first, answer later.** A grounding node that ends with "Do not answer the question
  itself" keeps exploration out of the answer node's context.
- **Forbid paste-through.** Report goals end with "never paste raw tool output or JSON as the
  answer" — the model otherwise terminates with its last observation.
- **Review independently.** Review nodes say "recompute from the calibers, do not reuse upstream
  SQL" — otherwise review degenerates into re-running the same query.
- **Bound the probes.** "metadata and bounded aggregates only, no full scans" keeps grounding
  nodes cheap and safe on business databases.

## Runtime behavior worth knowing

- **Parallel tool calls** in one model turn (native `tool_calls` or a joined text action) execute
  as a batch; the trace row shows the joined tool names and per-call observations.
- **Empty-argument guard**: a truncated turn that calls a tool with no arguments fails fast with
  an actionable observation ("was called with no arguments… retry with complete JSON") and the
  agent usually self-heals on the next turn; the card badges it *missing args · truncated* with a
  retry count.
- **Provider failures** (402/401/403, Insufficient Balance) fail the node loudly instead of being
  returned as a fake answer.
- **HTML rendering**: only `html_interpreter` produces report artifacts; one call per report, then
  terminate with a short summary. The rendered HTML is written to the session artifact directory
  and surfaces as a chip on the node card.
- **Output cap**: node model calls run with a 16k token output budget — enough for full HTML
  reports; the old 4k cap truncated tool arguments mid-string.

## Turn budgets

Budget per node complexity, keep the chain ≤ ~40 turns total: grounding 4–6, planning 4, analysis
8–10, review 6–8, report 6. A node that regularly hits its cap needs a tighter goal or smaller
scope, not a bigger cap.

Next: [data entry](./data-entry.md) · [confirmation gates](./human-confirm.md) · [custom operators](../custom-operator.md)
