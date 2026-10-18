# Observability

DB-GPT Observability gives you end-to-end visibility into how agents run — what they think, which tools they call, how much the model costs, and how long every step takes. It answers the question "what did the agent actually do?" without switching to an external tracing system.

## Core capabilities

### Overview dashboard

The Overview page (`/observability`) provides a high-level health snapshot over the last 24 hours:

- **KPIs** — number of agents, number of events, total tokens consumed, P95 latency, and error rate.
- **Token breakdown** — input tokens, output tokens, cache-hit tokens, and cache-miss tokens, summarizing the model usage of your agent runs.
- **Model usage table** — per-model aggregation: call count, input/output tokens, total tokens, and average latency.
- **Trend charts** — event volume and P95 latency over time.
- **Agent health** — per-agent event count and error rate.

### Trace list & trace detail

- **Trace list** (`/observability/traces`) lists each agent execution as a trace, filtering out pure-HTTP noise so only meaningful agent traces are shown.
- **Trace detail** (`/observability/traces/{trace_id}`) shows the full execution chain:
  - conversation ID (link back to the originating chat),
  - a collapsible span tree with `span_id` / `parent_span_id`, agent, model, cost, duration, and raw metadata.

### In-conversation Trace tab

Inside a chat session, the right panel has a **Trace** tab that renders the current conversation's execution as a **message-flow timeline**:

```
User question → System prompt → Thought → Tool call (input + output) → Reply
```

This mirrors how the messages actually looked to the model — task preview, reasoning, each tool call and its result — in one continuous stream, rather than a flat span tree.

## How it works

Observability is built on a pluggable read-side protocol — `ObservabilityProvider`:

- **Default backend (SQLite)** — works out of the box with zero external dependencies. Spans and events are written to an isolated `logs/observability.db` file, so high-volume telemetry never bloats the main business database.
- **Extensible** — the provider is selected by configuration (`provider_cls`), so alternative backends (e.g. a future ZizkaDB, OpenTelemetry, Prometheus) can be dropped in without changing the UI.

The write side reuses the existing `root_tracer` spans. Each agent turn, LLM call, and tool execution becomes a span carrying model name, token usage (prompt / completion / total), latency, cost, and status. Each message is linked to its trace via `trace_id` so a conversation can be joined to its execution trace.

## Key benefits

- **Zero-setup visibility** — runs on the default SQLite backend, no extra services required.
- **Traceability** — from a chat answer, drill into the exact tool calls, model tokens, and latency behind it.
- **Cost & latency awareness** — see token consumption and P95 latency at a glance.
- **Pluggable** — swap the backend via config without changing the UI pages.