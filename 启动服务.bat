@echo off
chcp 65001 >nul
title 注塑机台最优工艺卡 - 服务运行中

echo ============================================
echo   注塑机台最优工艺卡分析系统
echo ============================================
echo.
echo   服务正在启动...
echo.

cd /d "%~dp0"

C:\Users\rfuser\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true

pause