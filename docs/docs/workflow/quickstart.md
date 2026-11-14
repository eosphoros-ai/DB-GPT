# Quickstart: Create and Run a Workflow

This guide takes you from a built-in template to a workflow of your own, in about ten minutes.

## 1. Pick a template

Open **Task Flow → Built-in Templates**. Each card shows the node chain at a glance; **Run**
starts it in chat, **Edit a Copy** opens it in the editor as your own flow.

![Built-in template center](/img/workflow/en/fig-01-template-center.png)

The shipped set covers the DB domain:

- **DB Schema & Docs QA** — grounding → cited answer.
- **DB Data Fetch** — grounding/plan → SQL fetch with self-repair → verification & caliber notes.
- **DB Intelligent Analysis** — grounding → plan → pivot analysis → numeric review → HTML report.

## 2. Run it from chat

You can also start a workflow from the chat composer: open the attachment menu, pick the flow,
type your question and send. The selected flow appears as a chip above the composer.

![Composer with a workflow selected](/img/workflow/en/fig-02-flow-composer.png)

The run card appears immediately with the **full node chain** — nodes the DAG has not reached yet
render as dashed *pending* chips, so you always see the whole plan:

![Node chain with pending nodes](/img/workflow/en/fig-03-run-pending.png)

## 3. Read the result

When the run settles, each node card carries its trace and outputs. The report node registers its
HTML as an artifact chip — click the name to preview in the right rail, or the download icon to
save the file.

![Completed run with artifact chips](/img/workflow/en/fig-04-run-complete.png)
![HTML report preview in the right rail](/img/workflow/en/fig-05-html-preview.png)

## 4. Make it yours

**Edit a Copy** opens the editor with the template's nodes. Change a node's goal, swap its tools,
re-point its datasource, add or remove nodes — then **save and deploy**.

:::warning
Saving in the editor leaves the flow in `developing` (undeployed) state. Chat runs only pick up
`running` flows — deploy after editing, otherwise chat reports *dag not found*. See
[Troubleshooting](./troubleshooting.md).
:::

## 5. Reuse it

Deployed flows appear under **My Flows** and in the chat attachment menu. The first chat run of a
built-in template creates a personal instance; your edits never mutate the shipped template.

Next: [Editor guide](./editor.md) · [Node reference](./nodes/overview.md)
