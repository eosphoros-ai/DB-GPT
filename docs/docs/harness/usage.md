# Using the Harness

## Picking an engine

Open **Setting** at the bottom of the sidebar. The popover lists management entries and a
**HARNESS** section: each engine with its live availability, the current selection ticked, and
a one-line scope note.

![Harness selection in the Setting popover](/img/harness/en/fig-01-settings-harness.png)

- Selecting an engine persists server-side and applies to **new tasks** from any tab.
- Unavailable engines are greyed out with the probe reason (for example a missing pi CLI or
  an old Node runtime); selecting one is refused with a toast instead of failing mid-turn.
- The list is probed per request, so installing the pi CLI takes effect without restarting
  the server.

## pi prerequisites

The pi engine spawns the pi CLI as a subprocess per conversation:

- A `pi` executable discoverable via the `DBGPT_HARNESS_PI_CLI` env var, `pi` on `PATH`, or
  the known install locations; Node ≥ 22.19 is resolved from `PATH` or nvm installs
  (`DBGPT_HARNESS_PI_NODE` pins it explicitly).
- Each conversation gets an isolated workspace (`pi_workspace/<conv_id>`) and an isolated
  agent directory; DB-GPT built-in tools are bridged into pi as native tools and execute
  server-side through an internal token-protected endpoint.
- Destructive built-ins stay excluded by default (`DBGPT_HARNESS_PI_EXCLUDED_TOOLS`,
  default `bash`), mirroring the dbgpt engine's containment.

## Installing the pi runtime

The pi CLI is deliberately **not** part of DB-GPT's dependency manifests: it is an
out-of-band runtime the probe discovers per request. On a fresh machine the project
default (`pi`) therefore falls back to the built-in DB-GPT engine until the runtime
is installed.

One-shot installer (idempotent, sudo-free):

```bash
bash scripts/install_pi_runtime.sh
```

The script ensures a Node runtime ≥ 22.19 (reusing `DBGPT_HARNESS_PI_NODE`, `PATH`, or
existing nvm installs; installing Node 22 via nvm when nothing qualifies), then installs
`@earendil-works/pi-coding-agent` into `~/.dbgpt/pi-runtime` — one of the probe's known
locations. Override the npm registry with `NPM_REGISTRY` (for example
`https://registry.npmmirror.com`) and the install prefix with `PI_PREFIX`.

Manual equivalent:

```bash
nvm install 22
npm install -g --prefix ~/.dbgpt/pi-runtime @earendil-works/pi-coding-agent
```

Availability is probed per request, so `GET /api/v1/chat/harness/engines` shows
`pi.available: true` right after installation without a server restart. Note that a
persisted server preference (`harness_engine.json` in the server working directory)
outranks the project default: if it pins `dbgpt`, re-select pi in Setting or
`PUT /api/v1/chat/harness/engine`.

## Reading a run

Whichever engine runs the turn, the conversation surface is identical:

- **Timeline** — intent line, grouped tool rows and observations stream as the turn runs.
- **Trace** — the Trace entry in the artifact rail opens the synthesized span tree
  (thoughts, tool actions, terminate) for pi runs.
- **Artifacts** — query result sets render as inline data cards with the executed SQL, an
  edit-and-rerun entry point and CSV / Excel export; HTML reports preview in the rail.

![A query artifact produced by a pi run](/img/harness/en/fig-02-query-artifact.png)

- **Approvals** — high-risk calls raise the same confirmation dock; session/always memory
  behaves identically across engines.

## Per-request override (API)

Programmatic callers pin an engine per request:

```json
{
  "conv_uid": "<conversation>",
  "user_input": "top 5 stores by sales",
  "ext_info": { "harness_engine": "pi" }
}
```

Unknown or unavailable values fall through to the server preference, and an unavailable
explicit choice fails fast with a terminal message before any agent work starts.

## Troubleshooting

- `GET /api/v1/chat/harness/engines` returns the availability manifest the popover renders —
  the fastest way to see why pi is greyed out.
- A turn that starts and immediately ends with "engine unavailable" means the preference
  points at an engine whose probe now fails (CLI removed, Node downgraded); pick DB-GPT in
  Setting or fix the install.
