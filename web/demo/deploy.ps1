# 部署上 Cloudflare Pages（一鍵）
#
# 前置（只需做一次）：
#   1) 去 https://dash.cloudflare.com/ 開免費帳號（Pages 免費方案已夠）
#   2) 裝 Node 18+（本機已有 node），然後：
#        npx --yes wrangler login            # 瀏覽器授權
#        npx --yes wrangler pages project create prize-intel-beta --production-branch main
#
# 之後每次更新：
#   pwsh -File deploy.ps1
#
# 注意：dist/ 係 build_demo.py 生成，唔好手改。
param(
    [string]$Project = "prize-intel-beta",
    [string]$Branch  = "main"
)

$ErrorActionPreference = "Stop"
$dist = Join-Path $PSScriptRoot "dist"

if (-not (Test-Path (Join-Path $dist "index.html"))) {
    Write-Host "dist/index.html 唔存在，先跑：" -ForegroundColor Yellow
    Write-Host "  python prize-intel\web\demo\build_demo.py"
    exit 1
}

$size = [math]::Round(((Get-Item (Join-Path $dist "index.html")).Length / 1KB), 1)
Write-Host "上傳目錄：$dist （index.html ${size}KB）" -ForegroundColor Cyan
Get-ChildItem $dist -File | ForEach-Object { Write-Host ("  - {0}" -f $_.Name) }

# 快速網絡檢查（wrangler 需要連 Cloudflare API）
try {
    $null = Invoke-WebRequest -Uri "https://api.cloudflare.com" -Method Head -TimeoutSec 8 -UseBasicParsing
} catch {
    Write-Host "`n⚠️ 連唔到 api.cloudflare.com（可能冇網絡／被防火牆擋）。" -ForegroundColor Yellow
    Write-Host "   wrangler 一樣會失敗。請喺有網絡嘅環境再跑。"
    exit 2
}

Write-Host "`n開始部署…" -ForegroundColor Cyan
npx --yes wrangler@latest pages deploy $dist `
    --project-name $Project `
    --branch $Branch `
    --commit-dirty=true

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n部署失敗（exit $LASTEXITCODE）。常見原因：未 wrangler login / project 未建立。" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n✅ 部署完成。URL 通常係：" -ForegroundColor Green
Write-Host "   https://$Project.pages.dev"
Write-Host "   自訂網域／分支預覽喺 Cloudflare Dashboard → Pages → $Project 睇。"
Write-Host "`n回滾：Cloudflare Dashboard → Deployments → 揀上一個版本 → Rollback"
