---
title: Context Management
---

# Agent Context Management

Agent context management keeps long-running ReAct conversations inside the
model context window without losing the working state of the task. It tracks
token usage before each model call, emits live context status events, and applies
progressively stronger compaction when the conversation grows too large.

## Overview

```text
User task
   |
   v
Agent builds messages
system prompt + task progress + memory + recent ReAct rounds
   |
   v
Count tokens
ProxyTokenizerWrapper.count_token(model_name)
fallback: len(content) // 4
   |
   v
Compute budget
effective_budget = max_context_tokens - reserved_tokens
usage_ratio = used_tokens / effective_budget
   |
   v
Classify state
normal < warning < error < critical < overflow
   |
   +-- normal --------------------------------------+
   |                                                |
   v                                                |
Send messages to LLM                                |
                                                    |
warning or above                                    |
   |                                                |
   v                                                |
Layer 1: Observation micro-compaction               |
truncate old tool observations                      |
   |                                                |
   v                                                |
Recount and emit context.status                     |
   |                                                |
   +-- below warning -------------------------------+
   |                                                |
   v                                                |
Layer 2: Session memory compaction                  |
drop old ReAct rounds, keep recent rounds           |
   |                                                |
   v                                                |
Recount and emit context.status                     |
   |                                                |
   +-- below error ---------------------------------+
   |                                                |
   v                                                |
Layer 3: Full context compression                   |
summarize old rounds with the LLM                   |
   |                                                |
   v                                                |
Recount and emit context.status                     |
   |                                                |
   +----------------------------------------------->+

If the LLM still returns a context overflow error:

LLM context_too_long / maximum context length error
   |
   v
Layer 4: Reactive compaction
keep system prompt + last 2 ReAct rounds
   |
   v
Retry the model call once with the compacted messages
```

Tool results are preserved through a separate snapshot path:

```text
Action succeeds
   |
   v
Write full operation snapshot
step, action, action_input, observation, thought, timestamp
   |
   v
Store snapshot path on the memory fragment
and in task progress metadata
   |
   v
Rebuild memory for future prompts
Observation: short or compacted observation
[Full detail available at: /path/to/snapshot.json]
   |
   v
Layer 1 / Layer 2 can shrink prompt text
without deleting the original tool result file
```

## Token Budget

The context manager counts the tokens in the current `AgentMessage` list before
the model call. Counting uses `ProxyTokenizerWrapper` with the active
`model_name`. If the tokenizer cannot count the content, DB-GPT falls back to a
rough estimate of four characters per token.

The usable context window is:

```text
effective_budget = max_context_tokens - reserved_tokens
```

`reserved_tokens` keeps space for the model response so the prompt does not fill
the entire model window.

## States And Thresholds

| State | Default trigger | Meaning |
| --- | --- | --- |
| `normal` | `< 70%` | No compaction. |
| `warning` | `>= 70%` | Start lightweight compaction. |
| `error` | `>= 90%` | Use LLM-based summary compaction when needed. |
| `critical` | `>= 95%` | Same as error, but reported as a more urgent state. |
| `overflow` | `>= 100%` | Prompt is over the effective budget. |

After every count and every compaction layer, the backend emits a
`context.status` event with:

```json
{
  "type": "context.status",
  "used": 19000,
  "budget": 115904,
  "ratio": 0.164,
  "state": "normal",
  "compact_layer": null
}
```

The UI renders this as a compact context-window indicator.

## Compaction Layers

### Layer 1: Observation Micro-Compaction

Layer 1 is the lightest compaction. It only shortens old `Observation:` messages
from tool calls. Recent rounds are preserved in full.

Rules:

- Triggered when usage reaches `warning_threshold`.
- A round is considered old when it is older than
  `max_observation_age_rounds`.
- Old observations are truncated to `truncated_observation_max_chars`.
- If the observation has a snapshot path, the compacted message keeps a pointer
  to the full detail.

This layer is cheap and deterministic. It does not call the LLM.

### Layer 2: Session Memory Compaction

Layer 2 removes old complete ReAct rounds from the prompt. It relies on the
task-progress summary already injected into the system prompt, so the agent still
knows what has been completed.

Rules:

- Triggered when the prompt is still at or above `warning_threshold` after Layer
  1.
- Always keeps at least `min_keep_recent_rounds`.
- Also keeps enough recent content to satisfy `min_keep_tokens`.
- Drops complete old rounds rather than arbitrary individual messages.

This layer is also deterministic and does not call the LLM.

### Layer 3: Full Context Compression

Layer 3 summarizes old conversation rounds into a structured context summary
with the LLM, then keeps that summary plus the recent rounds.

Rules:

- Triggered when usage is at or above `error_threshold`.
- Keeps the last `min_keep_recent_rounds` unchanged.
- Summarizes older messages into one synthetic summary message.
- The summary prompt asks the model to preserve exact task state, paths, values,
  variable names, errors, and next steps.
- If summarization fails repeatedly, a circuit breaker stops retrying after
  `max_compact_failures`.

This layer is more expensive, but it preserves more semantic continuity than
simply dropping old messages.

### Layer 4: Reactive Compaction

Layer 4 is an emergency path. It is not triggered by the normal budget state
machine. Instead, it runs when the model call fails with a context overflow
error such as `context_too_long`, `context_length_exceeded`, or
`maximum context length`.

Rules:

- Keeps system messages.
- Keeps only the last two ReAct rounds.
- Relies on the task-progress summary in the system prompt to preserve task
  continuity.
- Retries the model call once with the compacted messages.

This layer is intentionally aggressive because it is only used after the model
has already rejected the prompt.

## Tool Result Snapshots

Tool observations can be large: SQL result tables, generated code output,
interpreter logs, file paths, report metadata, and intermediate computed values
may quickly dominate the prompt. DB-GPT keeps the prompt compact by separating
the full operation detail from the text that must stay in the model context.

When an action succeeds, the agent writes a JSON snapshot for the full operation.
The snapshot includes:

- `step`
- `action`
- `phase`
- `action_intention`
- `action_reason`
- `thought`
- `action_input`
- `observation`
- `timestamp`
- `conv_id`

By default, snapshots are written under:

```text
$DBGPT_HOME/workspace/op_snapshots/<conv_id>/
```

If `AgentContext.output_dir` is set, DB-GPT uses that directory instead.

Each snapshot file is named by step and action:

```text
step_003_sql_query.json
step_006_code_interpreter.json
```

The snapshot path is attached to the in-memory `AgentMemoryFragment` and also
recorded in the task-progress metadata. When the agent later rebuilds memories
into prompt messages, it appends a lightweight reference:

```text
Observation: <observation text>
[Full detail available at: /path/to/step_003_sql_query.json]
```

This matters during compaction:

- Layer 1 may truncate old `Observation:` text, but it preserves the snapshot
  reference when available.
- Layer 2 may remove old ReAct rounds from the prompt, but task progress still
  records the snapshot filename as a reference.
- Layer 3 summarizes old messages, while the original tool result remains on
  disk for exact recovery.

In other words, compaction reduces the prompt payload; it does not have to be
the only place where exact tool output lives.

## Configuration

Agent context management can be configured in the application TOML file:

```toml
[service.web.agent_context]
# Set to 0 to auto-detect from the selected model metadata.
max_context_tokens = 0
reserved_tokens = 4096
warning_threshold = 0.70
error_threshold = 0.90
critical_threshold = 0.95
min_keep_recent_rounds = 3
max_observation_age_rounds = 5
truncated_observation_max_chars = 200
min_keep_tokens = 10000
max_compact_failures = 3
```

When `max_context_tokens` is `0`, DB-GPT tries to read the selected model's
`context_length` from `llm_client.get_model_metadata(model_name)`. If the model
metadata is unavailable, it falls back to the default budget.

For stable behavior, set `context_length` on each LLM deployment:

```toml
[[models.llms]]
name = "Qwen/Qwen2.5-Coder-32B-Instruct"
provider = "proxy/siliconflow"
api_key = "${env:SILICONFLOW_API_KEY}"
context_length = 32768
```

With this setup, switching models also switches the effective context budget.

## Design Notes

- Layer 1 and Layer 2 are deterministic and cheap. They are preferred before
  any LLM summarization.
- Layer 3 uses the LLM only when the context is close to failure.
- Layer 4 is a last-resort retry path for model-side context overflow errors.
- The frontend receives `context.status` events independently from normal chat
  text, so UI indicators can update without polluting the conversation.
- Compaction is progressive: after each layer, DB-GPT recounts tokens and stops
  escalating if the prompt returns to a safe state.
