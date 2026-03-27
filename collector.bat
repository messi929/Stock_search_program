@echo off
echo ========================================
echo  Stock Screener Pro - Data Collector
echo ========================================
echo.
echo  1) 전체 수집 (1회)
echo  2) 스케줄 모드 (장중/장외 자동)
echo  3) KR 스냅샷만
echo  4) US 스냅샷만
echo  5) 히스토리 (KR + US)
echo  6) 종료
echo.
set /p choice=선택:

if "%choice%"=="1" (
    python collector.py --all
) else if "%choice%"=="2" (
    python collector.py --schedule
) else if "%choice%"=="3" (
    python collector.py --kr-snapshot
) else if "%choice%"=="4" (
    python collector.py --us-snapshot
) else if "%choice%"=="5" (
    python collector.py --history --us-history
) else (
    exit /b 0
)
pause
