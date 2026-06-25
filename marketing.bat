@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:menu
cls
echo ============================================
echo   Axis 마케팅 글 생성기 (스레드용)
echo ============================================
echo.
echo  종목을 비워두면 오늘 화제 종목을 자동 선정합니다.
echo  포맷: curiosity(호기심) contrarian(반대의견) trust(신뢰) cta(댓글모집)
echo        비워두면 기본 3종(curiosity,contrarian,cta).
echo.
set "tickers="
set "formats="
set /p tickers="종목 코드 (쉼표 구분, 예: 005930,000660): "
set /p formats="포맷 (쉼표 구분, 비우면 기본): "
echo.
echo --------------------------------------------
echo  생성 중... (종목당 약 2~5초, ~5원)
echo --------------------------------------------
py -m jobs.marketing_generate --tickers "%tickers%" --formats "%formats%"
echo.
echo  생성된 초안은 웹 관리자 콘솔 → 마케팅 탭에서 검수/복사할 수 있습니다.
echo.
choice /c YN /m "한 번 더 생성할까요? (Y/N)"
if errorlevel 2 goto end
goto menu

:end
echo.
echo 종료합니다.
timeout /t 2 >nul
