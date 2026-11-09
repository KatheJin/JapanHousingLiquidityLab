param(
    [ValidateSet('initial','incremental')][string]$Mode = 'initial',
    [int]$Target = 3000,
    [int]$MaxBatches = 200,
    [int]$MaxSeconds = 86400
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location -LiteralPath $projectRoot
try {
    $logFolder = Join-Path $projectRoot 'data/tokyo-collection/operator-logs'
    New-Item -ItemType Directory -Path $logFolder -Force | Out-Null
    $logPath = Join-Path $logFolder ((Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
    & .venv/Scripts/python.exe -X utf8 -m japan_housing_liquidity_lab.tokyo_collection collect --mode $Mode --target $Target --max-batches $MaxBatches --max-seconds $MaxSeconds 2>&1 | Tee-Object -FilePath $logPath
    $collectionExit = $LASTEXITCODE
    if ($collectionExit -ne 0) { throw "Collection stopped for review; inspect $logPath and data/tokyo-collection/status.json" }
} finally { Pop-Location }
