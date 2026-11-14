# What is a Workflow?

A **workflow** (TaskFlow) is a reusable, multi-agent pipeline that you invoke with one message in
chat. Instead of one generalist agent improvising every step, a workflow runs a declared chain of
focused nodes — grounding, fetching, analyzing, reviewing, reporting — where each node is an
independent agent with its own goal, tool boundary and output contract.

![A completed workflow run in chat](/img/workflow/en/fig-04-run-complete.png)

## Why workflows instead of a single agent

| | Single-agent chat | Workflow |
|---|---|---|
| Planning | Implicit, per conversation | Declared once, reused everywhere |
| Verification | Hope the agent double-checks | A dedicated review node recomputes key numbers |
| Tool safety | One big tool belt | Per-node tool boundary (checkboxes ARE the boundary) |
| Deliverables | Text in chat | First-class artifacts (HTML reports, query result sets) |
| Cost/latency control | Unbounded loop | Per-node turn budgets |

## The orchestration model

A workflow is a DAG compiled to AWEL at deploy time. Three channels connect the nodes:

- **Question channel** — the end user's original message is broadcast to every node, so each agent
  keeps the business question in view.
- **Control channel** — the declared edges enforce execution order; a node starts when its
  upstream control edge completes.
- **Data channel** — every node receives the *clean outputs of all prior nodes* (not just its
  direct parent), labelled with the source node name and kind, capped by a context budget.

Nodes never see each other's internal reasoning or tool traces — only final outputs. That is what
makes a node's **output contract** (the `Output:` line in its goal) the interface between nodes:
downstream agents parse upstream sections against those contracts.

## What you get in chat

- A **run card**: progress header, horizontal node chain (pending / running / success / failed),
  and one expandable card per node carrying its ReAct trace.
- **Artifacts**: HTML reports render as chips on the producing node (preview + download); SQL
  result sets render as inline query blocks with edit-and-rerun.
- **Confirmation gates**: a `human_confirm` node pauses the run and floats a dock above the
  composer until you approve.

## Where to go next

- [Quickstart](./quickstart.md) — run a built-in template, then make it yours.
- [Node reference](./nodes/overview.md) — what each node kind does.
- [Custom operators](./custom-operator.md) — from zero-code config to Python operators.
- [Runs & artifacts](./runs-and-artifacts.md) — how to read a run card.
