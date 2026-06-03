# feat(openrouter): native provider routing and multi-LLM config

## Summary

This PR adds first-class OpenRouter support for the `proxy/openai` client and ships an example TOML for running **two chat models** (OpenRouter + local OpenAI-compatible endpoint) and **two embedding providers** side by side.

It replaces fragile runtime patches that modified `chatgpt.py` inside Docker containers at startup.

**Scope:** model proxy + configuration only. No UI/i18n/agent changes (those live on `feature/i18n-ru-locale`).

## Motivation

[OpenRouter](https://openrouter.ai/docs) expects provider preference in the request body (`provider.order`, `allow_fallbacks`). The OpenAI Python SDK does not accept top-level `provider`; it must be sent via `extra_body`.

Without this change, setting `OPENROUTER_PROVIDER_ORDER` (e.g. `alibaba` for DeepSeek) has no effect, and requests may hit the wrong upstream provider or fail routing expectations.

## Changes

### 1. `packages/dbgpt-core/.../chatgpt.py`

In `OpenAILLMClient._build_request`, after applying `openai_kwargs`:

- Read `OPENROUTER_PROVIDER_ORDER` (comma-separated provider slugs).
- Read `OPENROUTER_ALLOW_FALLBACKS` (`true` / `false`).
- When order is set, attach to payload:

  ```json
  "extra_body": {
    "provider": {
      "order": ["alibaba"],
      "allow_fallbacks": false
    }
  }
  ```

Marked with comment `DBGPT_OPENROUTER_NATIVE` so deploy scripts can detect baked-in support.

**Behavior when env is unset:** no change to existing OpenAI/Azure proxy usage.

### 2. `configs/dbgpt-openrouter.toml`

Example configuration:

| Role | Source | Env vars |
|------|--------|----------|
| Primary LLM | OpenRouter | `OPENROUTER_*` |
| Secondary LLM | LM Studio / any OpenAI-compatible API | `LMSTUDIO_*` |
| Embeddings | OpenRouter + local | `OPENROUTER_EMBED_*`, `LMSTUDIO_EMBED_*` |

## Configuration

```bash
export DBGPT_CONFIG_FILE=dbgpt-openrouter.toml
export OPENROUTER_API_KEY=sk-or-...
export OPENROUTER_MODEL=deepseek/deepseek-v4-flash
export OPENROUTER_PROVIDER_ORDER=alibaba
export OPENROUTER_ALLOW_FALLBACKS=false

export LMSTUDIO_API_BASE=http://192.168.88.101:1238/v1
export LMSTUDIO_MODEL=openai/gpt-oss-20b
export LMSTUDIO_API_KEY=lm-studio
```

## Test plan

- [ ] Start webserver with `dbgpt-openrouter.toml` and valid `OPENROUTER_API_KEY`.
- [ ] `GET /api/v1/model/types` returns **at least two** LLM names (OpenRouter model + secondary if worker is reachable).
- [ ] Chat completion with default OpenRouter model succeeds.
- [ ] With `OPENROUTER_PROVIDER_ORDER` set, inspect logs/request payload: `extra_body.provider.order` present.
- [ ] Switch model in UI; agent/chat uses selected model (`LLMStrategyType.Priority`).
- [ ] Secondary LLM: smoke test when `LMSTUDIO_API_BASE` is reachable from the container network.
- [ ] Embeddings: knowledge/RAG smoke with OpenRouter embed model.
- [ ] Regression: plain `proxy/openai` to `api.openai.com` still works when `OPENROUTER_PROVIDER_ORDER` is **not** set.

### Private deploy (optional)

Combined with i18n branch via overlay (no merge required):

```bash
bash scripts/prepare_dbgpt_src.sh   # i18n branch + checkout openrouter files
docker compose build webserver
bash scripts/verify_openrouter_deploy.sh
```

## Compatibility

- **Backward compatible:** patch is gated on `OPENROUTER_PROVIDER_ORDER`; empty env → identical behavior.
- **Independent of i18n PR:** can be merged/released separately; deploy overlays `chatgpt.py` from this branch onto `feature/i18n-ru-locale` at build time.

## Related

- i18n (separate PR): `feature/i18n-ru-locale` → upstream [#3089](https://github.com/eosphoros-ai/DB-GPT/pull/3089)
- Fork: `algerdby/DB-GPT`

## Notes for reviewers

- This PR intentionally does **not** set default database, skills, or locale — ops concerns stay in `server-deploy/`.
- If upstream prefers env-driven config only, the TOML can remain in docs/examples; the `chatgpt.py` change is the minimal product fix.
