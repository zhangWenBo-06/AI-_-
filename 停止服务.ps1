# 停止注塑机台最优工艺卡服务
Write-Host "正在停止 Streamlit 服务..." -ForegroundColor Yellow

$processes = Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*streamlit*app.py*" -or $_.MainWindowTitle -like "*streamlit*"
}

if ($processes) {
    $processes | ForEach-Object {
        Stop-Process -Id $_.Id -Force
        Write-Host "  已停止进程 ID: $($_.Id)" -ForegroundColor Green
    }
    Write-Host "✅ 服务已停止" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到正在运行的 Streamlit 服务" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")