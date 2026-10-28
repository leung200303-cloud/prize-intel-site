# 需要真 Postgres 才能跑（本機 Docker 未安裝／shell 無網絡，暫時跑唔到）
# 用途：一鍵建 DB → 灌 schema → 灌 seed → 跑 40 項驗收測試
#
# 用法：
#   pwsh -File run_local.ps1                 # 用 Docker（需要 Docker Desktop + Linux container）
#   pwsh -File run_local.ps1 -UseLocalPg     # 用本機已安裝嘅 psql
#
param(
    [switch]$UseLocalPg,
    [string]$Container = "prize-intel-pg",
    [string]$PgUser    = "postgres",
    [string]$PgPassword = "dev",
    [string]$DbName    = "prize_intel",
    [int]$Port         = 5432
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Fail($msg) { Write-Host "FAILED: $msg" -ForegroundColor Red; exit 1 }

if ($UseLocalPg) {
    $psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
    if (-not $psql) { Fail "搵唔到 psql，請先安裝 PostgreSQL 或改用 Docker 模式" }
    Write-Host "使用本機 psql: $psql"
    $env:PGPASSWORD = $PgPassword
    & $psql -U $PgUser -c "DROP DATABASE IF EXISTS $DbName" 2>$null
    & $psql -U $PgUser -c "CREATE DATABASE $DbName"
    & $psql -U $PgUser -d $DbName -v ON_ERROR_STOP=1 -f (Join-Path $here "01_schema.sql")
    & $psql -U $PgUser -d $DbName -v ON_ERROR_STOP=1 -f (Join-Path $here "02_seed.sql")
    & $psql -U $PgUser -d $DbName -v ON_ERROR_STOP=1 -f (Join-Path $here "tests.sql")
    exit $LASTEXITCODE
}

$docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $docker) { Fail "搵唔到 docker。可以：1) 裝 Docker Desktop；2) 裝 PostgreSQL 後用 -UseLocalPg" }

# 確認係 Linux container engine（Windows container 模式跑唔到 postgres 官方 image）
$osType = (& $docker info --format '{{.OSType}}' 2>$null)
if ($osType -ne "linux") {
    Fail "Docker engine OSType = '$osType'，需要 linux。Windows container 模式冇 postgres 官方 image。"
}

& $docker rm -f $Container 2>$null | Out-Null
& $docker run -d --name $Container -e "POSTGRES_PASSWORD=$PgPassword" -p "${Port}:5432" postgres:16
if ($LASTEXITCODE -ne 0) { Fail "docker run 失敗" }

Write-Host "等 Postgres 起身..." -NoNewline
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    & $docker exec $Container pg_isready -U $PgUser -d postgres 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Write-Host "." -NoNewline
}
if (-not $ready) { Fail "Postgres 40×2s 內未 ready" }
Write-Host " ready"

& $docker exec $Container psql -U $PgUser -c "CREATE DATABASE $DbName"
foreach ($f in @("01_schema.sql", "02_seed.sql", "tests.sql")) {
    Write-Host "`n=== $f ===" -ForegroundColor Cyan
    Get-Content (Join-Path $here $f) -Raw -Encoding UTF8 |
        & $docker exec -i $Container psql -U $PgUser -d $DbName -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { Fail "$f 執行失敗" }
}

Write-Host "`n全部完成。連線：postgresql://${PgUser}:${PgPassword}@localhost:${Port}/${DbName}" -ForegroundColor Green
