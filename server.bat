@echo off
chcp 65001 >nul
echo ============================================
echo  Stock Screener Pro — Server Mode
echo ============================================
echo.

set PYTHONUTF8=1
set RUN_MODE=server
set ADMIN_KEY=your-admin-key-here

echo  모드: Server (크롤링 + DB + API)
echo  http://0.0.0.0:8501
echo.

py -m uvicorn screener.main:app --host 0.0.0.0 --port 8501

pause
