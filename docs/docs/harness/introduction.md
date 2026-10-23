# What is a Harness?

A **harness** is the execution runtime that drives an agent turn: it owns the model loop, the
tool calls, the streamed trace and the artifacts a turn produces. DB-GPT ships a harness layer
with **pluggable engines**, so the same conversation UI, tool containment, approval policy and
artifact surfaces can be driven by different runtimes.

![Harness selection in the Setting popover](/img/harness/en/fig-01-settings-harness.png)

## Built-in engines

| Engine | What it is | Availability |
|---|---|---|
| **DB-GPT** | The built-in ReAct / tool-calling loop. No external dependency; always available. | always |
| **pi** | An external CLI harness (`pi --mode rpc`) spawned per conversation. DB-GPT bridges its tools, models and approvals into the pi process. | requires the pi CLI and Node ≥ 22.19 |
| **DSH** | Reserved slot for a future engine. | coming soon |

Every engine shares the same contract with the product:

- **Tools** — the same scoped tool belt (SQL query, code/shell interpreter, HTML renderer,
  skills, knowledge) is exposed to the engine; the engine never escapes the containment.
- **Approvals** — high-risk tool calls go through the same policy engine and the same
  confirmation dock, no matter which engine proposed the call.
- **Artifacts** — HTML reports, query result sets and files surface as the same first-class
  artifact cards, rail entries and exports.
- **History** — turns persist in the same protocol payload, so reloading a conversation
  rebuilds the trace and the artifacts identically.

## How the engine is chosen

Resolution order for every new turn:

1. **Per-request override** — API callers may pin an engine with
   `ext_info.harness_engine` on the chat request.
2. **Server preference** — the value persisted by the Setting popover
   (`harness_engine.json` in the server working directory, written via
   `PUT /api/v1/chat/harness/engine`).
3. **Project default** — `pi` on fresh deployments, *availability-gated*: when the pi CLI
   cannot be discovered the default silently falls back to the built-in DB-GPT engine, so a
   bare deployment never starts into a dead engine.

The preference applies to **new tasks**; an existing conversation keeps the engine it started
with, which keeps traces and history coherent.

## Where to go next

- [Using the harness](usage.md) — picking an engine, pi prerequisites, reading a run.
- [Extending the harness](extending.md) — the adapter contract for adding engines such as
  DSH or Codex.
