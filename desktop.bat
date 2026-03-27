@echo off
chcp 65001 >nul
echo ============================================
echo  Stock Screener Pro
echo ============================================
echo.

set PYTHONUTF8=1
py desktop.py

pause
