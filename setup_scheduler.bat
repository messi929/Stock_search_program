@echo off
:: Stock Screener Pro — Windows 작업 스케줄러 등록/해제
:: 관리자 권한 필요

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 관리자 권한이 필요합니다.
    echo         이 파일을 우클릭 → "관리자 권한으로 실행" 해주세요.
    pause
    exit /b 1
)

set TASK_NAME=StockScreenerCollector
set PROJECT_DIR=%~dp0
set PYTHON_PATH=python

echo ========================================
echo  Stock Screener Pro - Scheduler Setup
echo ========================================
echo.
echo  현재 경로: %PROJECT_DIR%
echo.
echo  1) 스케줄러 등록 (로그인 시 자동 실행)
echo  2) 스케줄러 해제
echo  3) 상태 확인
echo  4) 종료
echo.
set /p choice=선택:

if "%choice%"=="1" goto :REGISTER
if "%choice%"=="2" goto :UNREGISTER
if "%choice%"=="3" goto :STATUS
exit /b 0

:REGISTER
echo.
echo [INFO] 작업 스케줄러에 등록 중...

:: 기존 작업 삭제 (있으면)
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: 로그인 시 자동 실행 등록
:: /sc ONLOGON: 로그인 시 실행
:: /delay 0001:00: 로그인 후 1분 대기 (네트워크 안정화)
:: /rl HIGHEST: 최고 권한
schtasks /create /tn "%TASK_NAME%" ^
    /tr "\"%PYTHON_PATH%\" \"%PROJECT_DIR%collector.py\" --schedule" ^
    /sc ONLOGON ^
    /delay 0001:00 ^
    /rl HIGHEST ^
    /f

if %errorlevel% equ 0 (
    echo [OK] 스케줄러 등록 완료!
    echo      작업명: %TASK_NAME%
    echo      실행: 로그인 시 collector.py --schedule 자동 시작
    echo      로그: %PROJECT_DIR%collector_*.log
) else (
    echo [ERROR] 등록 실패. 관리자 권한을 확인하세요.
)
echo.
pause
exit /b 0

:UNREGISTER
echo.
schtasks /delete /tn "%TASK_NAME%" /f
if %errorlevel% equ 0 (
    echo [OK] 스케줄러 해제 완료
) else (
    echo [INFO] 등록된 작업이 없습니다
)
echo.
pause
exit /b 0

:STATUS
echo.
schtasks /query /tn "%TASK_NAME%" /v /fo LIST 2>nul
if %errorlevel% neq 0 (
    echo [INFO] 등록된 작업 없음
)
echo.
pause
exit /b 0
