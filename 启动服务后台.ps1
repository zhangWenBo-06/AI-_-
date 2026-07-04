# 注塑机台最优工艺卡 - 后台启动脚本
# 右键此文件 → "使用 PowerShell 运行"
# 关闭此窗口后服务仍在后台运行

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "C:\Users\rfuser\AppData\Local\Programs\Python\Python312\python.exe"
$StreamlitExe = "C:\Users\rfuser\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe"

Write-Host "============================================" -ForegroundColor Green
Write-Host "  注塑机台最优工艺卡分析系统" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# 获取本机 IP
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -ne "WellKnown"
} | Select-Object -First 1).IPAddress

if (-not $ip) {
    $ip = "localhost"
}

Write-Host "  启动服务..." -ForegroundColor Yellow

# 后台启动 Streamlit
$process = Start-Process -FilePath $StreamlitExe `
    -ArgumentList "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true" `
    -WorkingDirectory $ScriptDir `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 5

# 检查是否启动成功
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 3
    Write-Host "  ✅ 服务启动成功!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  局域网访问地址: http://${ip}:8501" -ForegroundColor Cyan
    Write-Host "  本机访问地址:   http://localhost:8501" -ForegroundColor Cyan
    Write-Host "  进程 ID:        $($process.Id)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  停止服务: 任务管理器 → 结束 python.exe 进程" -ForegroundColor Gray
    Write-Host "  或在 PowerShell 中执行: Stop-Process -Id $($process.Id)" -ForegroundColor Gray
} catch {
    Write-Host "  ❌ 服务启动失败，请检查端口是否被占用" -ForegroundColor Red
}

Write-Host ""
Write-Host "按任意键关闭此窗口（服务仍在后台运行）..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")