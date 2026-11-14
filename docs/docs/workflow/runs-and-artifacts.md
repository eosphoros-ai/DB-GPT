# Reading Runs and Artifacts

Everything a workflow does is projected into one run card in the conversation, plus the global
status line at the end of the stream.

## The run card

- **Header** — flow name, progress bar `done / total nodes`, elapsed time.
- **Node chain** — one chip per node in execution order: dashed gray *pending*, amber pulsing
  *running*, green *success* with duration, red *failed*. The chain is seeded from the flow DSL at
  send time, so you see the whole plan before the first node finishes.
- **Node cards** — one per node, auto-expanded while running or failed:
  - trace rows: 💭 thinking, tool calls with arguments, collapsible 👁 observations, ✓ answer;
  - failure rows: red accent with the error collapsed behind a summary, plus badges
    (*missing args · truncated*, *execution failed*, *retry ×N*) when guards or retries fired;
  - artifact chips and query blocks (below).
- **Answer area** — below the card, only the final node's conclusion text. Intermediate node
  outputs stay inside their cards; vis/artifact fences never leak into prose.

![Running node card with ReAct trace](/img/workflow/en/fig-10-trace-card.png)

## Artifacts

### HTML reports

A node that renders HTML via `html_interpreter` registers a file artifact. The node card shows a
chip with the file name and size: click the name to open the interactive report in the right-rail
preview, click the download icon to save it. Files live under the session artifact directory and
are served only through the scoped artifact endpoint (pilot root boundary).

![HTML preview in the right rail](/img/workflow/en/fig-05-html-preview.png)

### Query result sets

`sql_query` results travel as structured chunks (SQL, columns, rows capped at 2000, truncation
flag, datasource). Inside a node card they render as an inline query block: the result table plus
an edit-and-rerun entry point that re-executes the SQL (tweaked or as-is) through the run
endpoint.

![Query artifact block inside a node card](/img/workflow/en/fig-11-query-artifact.png)

## Failure semantics

- A node that raises fails red; downstream nodes fail with it (they have no upstream contract to
  work from). The chain chip and card agree.
- Guarded retries (empty arguments, truncated turns) are *not* failures: the badge records them
  and the agent usually recovers within its turn budget.
- Provider-level errors (billing/auth/rate limit) fail the node honestly instead of surfacing as
  a fake analysis answer.
- If the stream dies before any node runs (e.g. the flow was undeployed), the UI shows the real
  server reason as a toast and in the answer area instead of a silent all-red chain.

## History

Completed runs keep their markers and artifact metadata in the stored conversation, so node cards,
traces and artifact chips survive page reloads. (Live-only caveat: re-attaching to a run that is
still executing server-side after a reload is not supported yet.)

Next: [troubleshooting](./troubleshooting.md) · [introduction](./introduction.md)
