@echo off
chcp 65001 >nul
echo ============================================
echo  Stock Screener Pro — 개발 서버
echo ============================================
echo.
echo http://localhost:8501
echo Press Ctrl+C to stop.
echo.

set PYTHONUTF8=1
py -m uvicorn screener.main:app --host 0.0.0.0 --port 8501 --reload

pause
