param([string]$PostgresBin = 'C:\posgresql\18\bin')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location -LiteralPath $projectRoot
try {
    & .venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin start --bin $PostgresBin
    if ($LASTEXITCODE -ne 0) { throw 'Local PostgreSQL startup failed; inspect ignored operator.log' }
    & .venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Schema upgrade failed' }
    Write-Host 'Local PostgreSQL ready. Collection and UI deployment are separate operations.'
} finally { Pop-Location }
