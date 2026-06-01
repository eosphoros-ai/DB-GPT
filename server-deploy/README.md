# Server deploy (private instance)

Deployment assets for a RU-localized DB-GPT instance (Docker Compose, entrypoint patches).

- **Not required** once agent i18n is in the main app image (`_agent_thinking_title` in `agentic_data_api.py`).
- Set `LANGUAGE=ru` / `DBGPT_LANG=ru` in compose; build web static with `scripts/build_web_static.sh`.

Official contributions: agent/UI i18n fixes go to the main repo via PR; this folder stays on the fork for ops.
