#!/usr/bin/env python3
"""Заменить секцию webserver в docker-compose.yml — без i18n-патчей."""
from pathlib import Path
import re
import sys

COMPOSE = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/algerd/dbgpt-deploy/docker-compose.yml")

NEW_WEB = """  webserver:
    build:
      context: /home/algerd
      dockerfile: dbgpt-deploy/Dockerfile.dbgpt
    image: dbgpt-local:latest
    container_name: dbgpt-webserver
    command: ["/bin/sh", "/app/scripts/entrypoint-dbgpt.sh"]
    environment:
      DBGPT_CONFIG_FILE: ${DBGPT_CONFIG_FILE:-dbgpt-docker.toml}
      MYSQL_HOST: db
      MYSQL_PORT: "3306"
      MYSQL_DATABASE: ${MYSQL_DATABASE:-dbgpt}
      MYSQL_USER: root
      MYSQL_PASSWORD: ${MYSQL_ROOT_PASSWORD:-aa123456}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      OPENROUTER_API_BASE: ${OPENROUTER_API_BASE:-https://openrouter.ai/api/v1}
      OPENROUTER_MODEL: ${OPENROUTER_MODEL:-deepseek/deepseek-v4-flash}
      OPENROUTER_PROVIDER_ORDER: ${OPENROUTER_PROVIDER_ORDER:-alibaba}
      OPENROUTER_ALLOW_FALLBACKS: ${OPENROUTER_ALLOW_FALLBACKS:-false}
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
      OPENROUTER_EMBED_MODEL: ${OPENROUTER_EMBED_MODEL:-openai/text-embedding-3-small}
      OPENROUTER_EMBED_API_URL: ${OPENROUTER_EMBED_API_URL:-https://openrouter.ai/api/v1/embeddings}
      LMSTUDIO_API_BASE: ${LMSTUDIO_API_BASE:-http://192.168.88.101:1238/v1}
      LMSTUDIO_MODEL: ${LMSTUDIO_MODEL:-openai/gpt-oss-20b}
      LMSTUDIO_API_KEY: ${LMSTUDIO_API_KEY:-lm-studio}
      LMSTUDIO_EMBED_MODEL: ${LMSTUDIO_EMBED_MODEL:-text-embedding-nomic-embed-text-v1.5}
      LMSTUDIO_EMBED_API_URL: ${LMSTUDIO_EMBED_API_URL:-http://192.168.88.101:1238/v1/embeddings}
      LANGUAGE: ${LANGUAGE:-ru}
      DBGPT_LANG: ${DBGPT_LANG:-ru}
      DBGPT_DEFAULT_DATABASE: ${DBGPT_DEFAULT_DATABASE:-fmcg}
      TZ: ${TZ:-Europe/Moscow}
      LC_ALL: C.UTF-8
      LC_TIME: ru_RU.UTF-8
      DBGPT_LLM_MODEL: ${DBGPT_LLM_MODEL:-gpt-4o-mini}
      DBGPT_LLM_PROVIDER: ${DBGPT_LLM_PROVIDER:-proxy/openai}
      DBGPT_EMBED_MODEL: ${DBGPT_EMBED_MODEL:-text-embedding-3-small}
    volumes:
      - ./configs:/app/configs:ro
      - ./overrides/auto_execute_prompt.py:/app/packages/dbgpt-app/src/dbgpt_app/scene/chat_db/auto_execute/prompt.py:ro
      - ./scripts/patch_openrouter_provider.py:/app/scripts/patch_openrouter_provider.py:ro
      - ./scripts/fix_db_default_outer.py:/app/scripts/fix_db_default_outer.py:ro
      - ./scripts/entrypoint-dbgpt.sh:/app/scripts/entrypoint-dbgpt.sh:ro
      - ./skills/walmart-sales-analyzer:/app/skills/walmart-sales-analyzer:ro
      - ./skills/financial-report-analyzer:/app/skills/financial-report-analyzer:ro
      - ./skills/csv-data-analysis:/app/skills/csv-data-analysis:ro
      - ./skills/skill-creator:/app/skills/skill-creator:ro
      - ./skills/agent-browser:/app/skills/agent-browser:ro
      - dbgpt-pilot-data:/app/pilot/data
      - dbgpt-pilot-message:/app/pilot/message
    ports:
      - "5670:5670"
    depends_on:
      db:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      fmcg-loader:
        condition: service_completed_successfully
    restart: unless-stopped
    networks:
      - dbgptnet
    healthcheck:
      test: ["CMD-SHELL", "python -c \\"import urllib.request; urllib.request.urlopen('http://127.0.0.1:5670/', timeout=5)\\""]
      interval: 15s
      timeout: 10s
      retries: 30
      start_period: 180s
"""

def main() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    text, n = re.subn(
        r"  webserver:.*?(?=\n  register-datasource:)",
        NEW_WEB + "\n",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n != 1:
        raise SystemExit(f"webserver block not replaced (n={n})")
    COMPOSE.write_text(text, encoding="utf-8")
    print("docker-compose.yml: webserver updated (no i18n patches)")


if __name__ == "__main__":
    main()
