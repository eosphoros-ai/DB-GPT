# Server deploy (private instance)

Deployment for RU-localized DB-GPT with OpenRouter + LM Studio, without mixing concerns in git forks.

## Fork boundaries

| Fork branch | Purpose |
|-------------|---------|
| `feature/i18n-ru-locale` | RU UI, agent SQL/CH messages, `AgentContext.language`, web static |
| `feature/openrouter-multi-llm` | `chatgpt.py` `extra_body.provider`, `configs/dbgpt-openrouter.toml` |
| This folder (`server-deploy/`) | Compose, Dockerfile, ops (`fix_db_default_outer`, skills) |

Upstream PR for i18n only: https://github.com/eosphoros-ai/DB-GPT/pull/3089

## Build flow

1. `prepare_dbgpt_src.sh` — checkout i18n, overlay OpenRouter files from second branch (no merge).
2. `docker compose build webserver` — Dockerfile copies web (ru), `agentic_data_api.py`, `chatgpt.py`.
3. Entrypoint runs only `fix_db_default_outer.py` (default DB `fmcg`).

```bash
cd /home/algerd/dbgpt-deploy
bash scripts/upgrade_from_fork.sh
# or
bash scripts/prepare_dbgpt_src.sh && docker compose build webserver && docker compose up -d --force-recreate webserver
bash scripts/verify_openrouter_deploy.sh
```

## Config

- `configs/dbgpt-openrouter.toml` — mounted to `/app/configs/`; set `DBGPT_CONFIG_FILE=dbgpt-openrouter.toml` in compose.
- `.env`: `OPENROUTER_API_KEY`, `OPENROUTER_PROVIDER_ORDER`, `LMSTUDIO_*`, `LANGUAGE=ru`, `DBGPT_LANG=ru`.

## Deprecated runtime patches

No longer used when image is built with `prepare_dbgpt_src.sh`:

- `patch_openrouter_provider.py` — replaced by `DBGPT_OPENROUTER_NATIVE` in `chatgpt.py`
- `patch_agentic_ru_strings.py`, `repair_agentic_api_syntax.py` — replaced by i18n fork + Dockerfile COPY

Kept in repo for old images only.

## Regression checklist

`scripts/verify_openrouter_deploy.sh`:

- HTTP 200 on `/`
- `/api/v1/model/types` lists OpenRouter and LM Studio model names
- `DBGPT_OPENROUTER_NATIVE` in container `chatgpt.py`
- No `思考中` in `agentic_data_api.py`

Manual: new agent dialog (RU steps), SQL to MySQL/CH `fmcg`, switch model in UI.
