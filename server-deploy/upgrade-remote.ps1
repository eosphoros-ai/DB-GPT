# Обновление DB-GPT на 192.168.88.77: чистый ru-i18n из OriginalDBTGPT, без patch-скриптов
param(
    [string]$HostAddr = "192.168.88.77",
    [string]$User = "algerd",
    [string]$Password = "zakis@82",
    [string]$RemoteDeploy = "/home/algerd/dbgpt-deploy",
    [string]$RemoteSrc = "/home/algerd/dbgpt-src"
)

$ErrorActionPreference = "Stop"
$Plink = "C:\Program Files\PuTTY\plink.exe"
$Pscp = "C:\Program Files\PuTTY\pscp.exe"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$LocalDeploy = $PSScriptRoot

function Invoke-Remote([string]$Command) {
    & $Plink -batch -ssh "${User}@${HostAddr}" -pw $Password $Command
    if ($LASTEXITCODE -ne 0) { throw "Remote failed: $Command" }
}

Write-Host "=== 1. Upload web + i18n source ==="
Invoke-Remote "mkdir -p $RemoteSrc"
$TarWeb = Join-Path $env:TEMP "dbgpt-web-src.tgz"
if (Test-Path $TarWeb) { Remove-Item $TarWeb -Force }
Push-Location $RepoRoot
tar --exclude=node_modules --exclude=.next --exclude=out -czf $TarWeb web i18n/locales/ru
Pop-Location
& $Pscp -batch -pw $Password $TarWeb "${User}@${HostAddr}:${RemoteSrc}/dbgpt-src.tgz"
if ($LASTEXITCODE -ne 0) { throw "SCP web failed" }
Invoke-Remote "cd $RemoteSrc && rm -rf web i18n && tar -xzf dbgpt-src.tgz && rm -f dbgpt-src.tgz && test -d web/locales/ru"

Write-Host "=== 2. Upload deploy scripts + Dockerfile ==="
& $Pscp -batch -pw $Password `
    "$LocalDeploy\Dockerfile.dbgpt" `
    "$LocalDeploy\scripts\prepare_web_deploy.py" `
    "$LocalDeploy\scripts\build_web_static.sh" `
    "$LocalDeploy\scripts\entrypoint-dbgpt.sh" `
    "$LocalDeploy\scripts\patch_openrouter_provider.py" `
    "$LocalDeploy\scripts\fix_db_default_outer.py" `
    "${User}@${HostAddr}:${RemoteDeploy}/"
if ($LASTEXITCODE -ne 0) { throw "SCP deploy failed" }
Invoke-Remote "mv $RemoteDeploy/prepare_web_deploy.py $RemoteDeploy/scripts/ 2>/dev/null; mv $RemoteDeploy/build_web_static.sh $RemoteDeploy/scripts/ 2>/dev/null; mv $RemoteDeploy/entrypoint-dbgpt.sh $RemoteDeploy/scripts/ 2>/dev/null; mv $RemoteDeploy/patch_openrouter_provider.py $RemoteDeploy/scripts/ 2>/dev/null; mv $RemoteDeploy/fix_db_default_outer.py $RemoteDeploy/scripts/ 2>/dev/null; chmod +x $RemoteDeploy/scripts/*.sh; sed -i 's/\r$//' $RemoteDeploy/Dockerfile.dbgpt $RemoteDeploy/scripts/*"

Write-Host "=== 3. Patch docker-compose (clean webserver, no i18n patches) ==="
$PatchCompose = @'
python3 << 'PYEOF'
from pathlib import Path
import re

p = Path("/home/algerd/dbgpt-deploy/docker-compose.yml")
text = p.read_text(encoding="utf-8")

new_web = r'''  webserver:
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
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:5670/', timeout=5)\""]
      interval: 15s
      timeout: 10s
      retries: 30
      start_period: 180s
'''

text, n = re.subn(
    r"  webserver:.*?(?=\n  register-datasource:)",
    new_web + "\n",
    text,
    count=1,
    flags=re.DOTALL,
)
if n != 1:
    raise SystemExit(f"webserver block not replaced (n={n})")
p.write_text(text, encoding="utf-8")
print("docker-compose.yml: webserver updated (no i18n patches)")
PYEOF
'@
Invoke-Remote $PatchCompose

Write-Host "=== 4. Archive old patch scripts ==="
Invoke-Remote "mkdir -p $RemoteDeploy/scripts/legacy-patches && for f in patch_ru_full.py patch_agentic_ru.py patch_web_source_ru.py apply_zh_ru_patch.py patch_bundle_*.py patch_moment_ru.py patch_ui_default_ru.py patch_i18n_t_calls.py patch_cache_bust.py patch_construct_ui_ru.py patch_antd_locale_ru.py patch_create_app_modal.py patch_timezone_ru.py patch_team_mode_backend.py patch_agent_ui_fixes.py patch_csv_data_analysis_ru.py patch_react_agent_ru.py patch_agentic_react_ru.py prepare_web_ru_build.py build_web_static_ru.sh; do [ -f $RemoteDeploy/scripts/`$f ] && mv $RemoteDeploy/scripts/`$f $RemoteDeploy/scripts/legacy-patches/ 2>/dev/null; done; echo legacy done"

Write-Host "=== 5. Rebuild webserver only (MySQL/CH volumes preserved) ==="
Invoke-Remote "cd $RemoteDeploy && docker compose build --no-cache webserver 2>&1 | tail -30"
Invoke-Remote "cd $RemoteDeploy && docker compose up -d webserver && sleep 5 && docker compose ps webserver"

Write-Host "=== 6. Refresh ClickHouse datasource registration ==="
Invoke-Remote "cd $RemoteDeploy && REGISTER_MODE=refresh docker compose run --rm register-datasource 2>&1 | tail -15"

Write-Host "Done: http://${HostAddr}:5670"
