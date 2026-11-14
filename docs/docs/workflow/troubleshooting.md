# Troubleshooting Workflows

Symptom-first index for the failures that actually happen in production use.

## Every node shows *failed* at 0:00 and a toast names a server error

The stream ended before any node produced a marker — usually `[SERVER_ERROR] Flow …'s dag id not
found`:

- The flow is in `developing` state (saved in the editor but not deployed). Open the editor and
  deploy, or redeploy via the flow API.
- The flow was deployed but the server process restarted before registration completed; `running`
  flows re-register at startup — retry once, and check the flow's state badge if it persists.

The UI shows the real reason as a toast and in the answer area; an all-red chain with *no* message
means an older frontend build.

## The report node renders no HTML / answers with raw JSON

- **Raw JSON in the answer**: the model terminated with its last tool observation pasted as the
  result. Current builds salvage envelopes to readable text and template goals forbid
  paste-through; if you see it on a custom flow, add the same sentence to the report goal.
- **`No HTML content provided` observations**: the HTML tool argument was truncated (output cap)
  or empty. Node model calls run with a 16k output budget; if you overrode `model` to a provider
  with a smaller cap, split the report or simplify the HTML.

## *missing args · truncated* badge with retry

A model turn was cut mid-protocol and called a tool with no arguments. The guard returns an
actionable observation and the agent retries — the badge is informational. Frequent occurrences
mean the node's payloads are too large: tighten the goal, cap rows, or raise `max_turns` rather
than ignoring it.

## `sql_query` says the datasource is out of scope / missing

The node's `datasources` config is the boundary: empty means no SQL tool at all, and a name not in
the datasource registry fails at tool build. With multiple datasources bound, the tool requires an
explicit `db_name` argument — grounding goals should state which database to use. Note that the
composer's database attachment does **not** feed workflows; only the node config does.

## Model provider errors (402 / 401 / 429)

Nodes fail loudly with the provider message instead of fabricating analysis. Check the model
provider balance/quota and rerun; the run card shows which node hit it.

## Template edits don't appear in chat

- Built-in templates instantiate into My Flows on first use (cached per browser). Changing a
  template file only affects new instances; the cache key bumps when template creation parameters
  change.
- Editing *your instance* requires a deploy afterwards (see the 0:00 failure above).

## A flow conversation won't reopen from its URL

Flow runs are live-streamed and their replay-from-history entry point is not shipped yet; the
conversation list shows the run but deep-linking a flow conversation lands on the home page.
Track it as a known gap, not a broken install.

Next: [runs & artifacts](./runs-and-artifacts.md) · [editor](./editor.md)
