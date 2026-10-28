# 起一個純靜態 server（唔需要 Node，唔需要 DB）
# 用法：pwsh -File serve.ps1        → http://127.0.0.1:8765/
param([int]$Port = 8765)

$py = "C:\Users\loljhhj\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "Serving http://127.0.0.1:$Port/  (Ctrl+C 停止)" -ForegroundColor Green
Write-Host "提示：都可以直接雙擊 standalone.html，唔使 server。"
& $py -m http.server $Port --bind 127.0.0.1 --directory $PSScriptRoot
