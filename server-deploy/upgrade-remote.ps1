# Обновление DB-GPT на 192.168.88.77: i18n + OpenRouter overlay, без legacy-патчей
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
$LocalDeploy = $PSScriptRoot

function Invoke-Remote([string]$Command) {
    & $Plink -batch -ssh "${User}@${HostAddr}" -pw $Password $Command
    if ($LASTEXITCODE -ne 0) { throw "Remote failed: $Command" }
}

Write-Host "=== 1. Upload deploy assets ==="
& $Pscp -batch -pw $Password -r `
    "$LocalDeploy\Dockerfile.dbgpt" `
    "$LocalDeploy\docker-compose.yml" `
    "$LocalDeploy\configs" `
    "$LocalDeploy\scripts" `
    "${User}@${HostAddr}:${RemoteDeploy}/"
if ($LASTEXITCODE -ne 0) { throw "SCP deploy failed" }
Invoke-Remote "chmod +x $RemoteDeploy/scripts/*.sh; sed -i 's/\r$//' $RemoteDeploy/Dockerfile.dbgpt $RemoteDeploy/docker-compose.yml $RemoteDeploy/scripts/* $RemoteDeploy/scripts/*.sh 2>/dev/null; true"

Write-Host "=== 2. Upgrade from fork (prepare_dbgpt_src + build + verify) ==="
Invoke-Remote "cd $RemoteDeploy && bash scripts/upgrade_from_fork.sh 2>&1 | tail -50"

Write-Host "Done: http://${HostAddr}:5670 (Ctrl+Shift+R)"
