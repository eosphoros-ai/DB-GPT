# Clean deploy: OriginalDBTGPT ru UI, old volumes, no i18n patches
param(
    [string]$HostAddr = "192.168.88.77",
    [string]$User = "algerd",
    [string]$Password = "zakis@82"
)

$ErrorActionPreference = "Stop"
$Plink = "C:\Program Files\PuTTY\plink.exe"
$Pscp = "C:\Program Files\PuTTY\pscp.exe"
$Repo = "z:\Projects\OriginalDBTGPT\DB-GPT"
$Deploy = "$Repo\server-deploy"
$Tar = Join-Path $env:TEMP "dbgpt-src-clean.tgz"

function Invoke-Remote([string]$Cmd) {
    & $Plink -batch -ssh "${User}@${HostAddr}" -pw $Password $Cmd
    if ($LASTEXITCODE -ne 0) { throw "Remote failed" }
}

Write-Host "Step 1: sync web + i18n/ru"
Remove-Item $Tar -ErrorAction SilentlyContinue
Push-Location $Repo
tar --exclude=node_modules --exclude=.next --exclude=out -czf $Tar web i18n/locales/ru
Pop-Location
& $Pscp -batch -pw $Password $Tar "${User}@${HostAddr}:/home/algerd/dbgpt-src-clean.tgz"

Write-Host "Step 2: unpack sources"
Invoke-Remote "cd /home/algerd && tar -xzf dbgpt-src-clean.tgz && cp -a web/* dbgpt-src/web/ && cp -a i18n/locales/ru/* dbgpt-src/i18n/locales/ru/ && rm -f dbgpt-src/web/pages/storage.ts dbgpt-src/web/pages/ctx-axios.ts && rm -f dbgpt-src-clean.tgz"

Write-Host "Step 3: upload deploy configs"
& $Pscp -batch -pw $Password `
    "$Deploy\docker-compose.yml" `
    "$Deploy\Dockerfile.dbgpt" `
    "$Deploy\scripts\prepare_web_deploy.py" `
    "$Deploy\scripts\build_web_static.sh" `
    "$Deploy\scripts\entrypoint-dbgpt.sh" `
    "$Deploy\scripts\clean_deploy.sh" `
    "$Deploy\scripts\fix_fmcg_user_id.py" `
    "$Deploy\scripts\patch_openrouter_provider.py" `
    "$Deploy\scripts\fix_db_default_outer.py" `
    "${User}@${HostAddr}:/home/algerd/dbgpt-deploy/"
& $Pscp -batch -pw $Password `
    "z:\Projects\DBTGPT\deploy\scripts\register_clickhouse.py" `
    "z:\Projects\DBTGPT\deploy\scripts\post_deploy_fmcg.sh" `
    "${User}@${HostAddr}:/home/algerd/dbgpt-deploy/scripts/"
if (Test-Path "$Deploy\skills\fmcg-analyst\SKILL.md") {
    & $Pscp -batch -pw $Password -r "$Deploy\skills\fmcg-analyst" "${User}@${HostAddr}:/home/algerd/dbgpt-deploy/skills/"
}

Invoke-Remote "bash -c 'cd /home/algerd/dbgpt-deploy && mkdir -p scripts && for f in prepare_web_deploy.py build_web_static.sh entrypoint-dbgpt.sh patch_openrouter_provider.py fix_db_default_outer.py fix_fmcg_user_id.py clean_deploy.sh; do [ -f \"\$f\" ] && mv -f \"\$f\" scripts/; done && sed -i \"s/\r$//\" docker-compose.yml scripts/*.sh scripts/*.py 2>/dev/null; chmod +x scripts/clean_deploy.sh'"

Write-Host "Step 4: start clean_deploy.sh on server (build ~10 min)"
Invoke-Remote "nohup /home/algerd/dbgpt-deploy/scripts/clean_deploy.sh > /tmp/clean_deploy.log 2>&1 & echo started"

Write-Host "Monitor: plink ${User}@${HostAddr} tail -f /tmp/clean_deploy.log"
Write-Host "URL: http://${HostAddr}:5670"
