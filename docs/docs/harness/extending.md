# Extending the Harness: Adding an Engine

An engine is an adapter between DB-GPT's product contract (SSE stream, tools, approvals,
artifacts, history) and an external or internal agent runtime. The pi adapter
(`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/harness_pi_stream.py`) is the reference
implementation; a Codex- or DSH-style engine follows the same six seams.

## The contract at a glance

| Seam | What the product expects | pi reference |
|---|---|---|
| Identity & availability | Engine id in `KNOWN_ENGINES`; probe entry in `engine_availability()` (`name`, `available`, `detail`) | `_probe_pi_cli()` (CLI + Node ≥ 22.19) |
| Selection | Honors `ext_info.harness_engine` → server preference → project default; listed automatically in the Setting popover | `resolve_harness_engine()` |
| Stream | SSE events the web client parses (below) | pi rpc frames → step events |
| Tools | Scoped tool belt with approval gate and read-only containment | `tool_bridge.register_conv_tools()` + `/v1/chat/harness/tool/run` |
| Artifacts | Envelope chunks promoted uncapped (html / image / query), files via the artifact-file endpoint | `_embedded_artifact_outputs()` |
| History | Protocol-v2 payload (steps + outputs) so reload rebuilds trace and artifacts | storage conversation writer |

## Step 1 — Register the engine

Add the id to `KNOWN_ENGINES` and an availability probe to `engine_availability()`. The probe
runs per request, so installing the engine's CLI must not require a server restart. The
Setting popover, the preference endpoint and the fail-fast gate all derive from these two
places — nothing else in the UI needs to change.

## Step 2 — Resolve and gate

Reuse `resolve_harness_engine()`-style resolution. If your engine should be the project
default for fresh deployments, follow the availability-gated pattern of
`_default_harness_engine()`: default to the new engine only when its probe succeeds, else
fall back to `dbgpt`. Always fail fast with a terminal stream message when an explicitly
requested engine is unavailable, before any agent work starts.

## Step 3 — Stream adapter

Emit the SSE contract the web client already parses; anything else is silently dropped:

- `step.start` / `step.meta` (thought, action, action_input, intention) / `step.done`
- `step.chunk` with `output_type` in `thought | text | markdown | code | html | image |
  file | query | table`
- human-in-the-loop frames: `approval.requested` / `approval.resolved` / `approval.intent`,
  `question.asked` / `question.replied` / `question.rejected`
- the final protocol-v2 payload that persists steps and outputs for history replay

Tool results travel as `{"chunks": [{"output_type": ..., "content": ...}]}` envelopes; keep
display text capped for the model/UI but promote full artifact payloads uncapped (see
Step 5).

## Step 4 — Bridge the tools

Two options, in order of preference:

1. **HTTP tool-run bridge (pi pattern).** Register the conversation's tool pack server-side,
   hand the engine a manifest of tool names + JSON schemas, and execute calls through an
   internal token-protected endpoint. The approval gate lives on that endpoint, so every
   engine inherits policy, deny/confirm tiers and session/always memory for free.
2. **Native function-calling.** If the engine speaks OpenAI-style tools, serialize the same
   tool pack as schemas and route every call through the same gate before execution.

Keep containment rules engine-agnostic: read-only SQL, sandboxed code/shell, excluded
destructive built-ins by default.

## Step 5 — Promote artifacts

When a tool envelope carries `html`, `image` or `query` chunks, promote them to typed stream
outputs **uncapped** (the pi adapter's `_embedded_artifact_outputs`), and persist them into
the step outputs. File artifacts written to the session workspace surface through the
scoped artifact-file endpoint; do not inline binaries into the stream.

## Step 6 — Persist history and trace

Write the protocol-v2 turn payload (steps with outputs, citations, final content) so a page
reload rebuilds the timeline and artifact cards. If the engine exposes its own trace,
synthesize spans (root + per-action) the Trace viewer can render, as `_write_pi_trace` does.

## Skeleton: a Codex-style adapter

```python
KNOWN_ENGINES = ("dbgpt", "pi", "dsh", "codex")

def _probe_codex() -> tuple[bool, str]:
    path = shutil.which("codex")
    return (True, path) if path else (False, "codex CLI not found")

async def stream_codex_turn(dialogue) -> AsyncIterator[str]:
    engine = resolve_harness_engine(dialogue)
    if engine == "codex" and not _probe_codex()[0]:
        yield terminal_message("engine codex unavailable")  # fail fast
        return
    conv = open_storage_conversation(dialogue)
    manifest = tool_bridge.register_conv_tools(dialogue.conv_uid, dialogue.ext_info, app)
    async for frame in codex_client.run(prompt=dialogue.user_input, tools=manifest):
        for event in translate_to_sse_contract(frame):   # step.* / approval.* / chunks
            yield sse(event)
        for artifact in promote_envelope_chunks(frame):  # html / image / query, uncapped
            yield sse(artifact)
    persist_protocol_v2(conv, steps, outputs, final_content)
```

## Checklist

- [ ] id in `KNOWN_ENGINES`, probe in `engine_availability()` (no restart to pick up installs)
- [ ] resolution order honored; unavailable explicit choice fails fast
- [ ] SSE contract emitted; unknown event types never leak to the client
- [ ] tools bridged through the approval gate; containment parity with dbgpt/pi
- [ ] html / image / query artifacts promoted uncapped and persisted
- [ ] protocol-v2 history written; Trace spans synthesized where the engine has them
- [ ] unit tests for probe + resolution (see `tests/test_harness_engine_default.py`)
- [ ] SSE end-to-end capture asserting `step.chunk output_type=query`-style payloads
