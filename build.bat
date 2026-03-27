@echo off
chcp 65001 >nul
echo ============================================
echo  Stock Screener Pro - Build
echo ============================================
echo.
echo  [1] Client 빌드 (배포용, 경량)
echo  [2] Server 빌드 (전체, 개발/테스트용)
echo.
set /p choice="선택 (1 또는 2): "

set PYTHONUTF8=1

if "%choice%"=="1" (
    echo.
    echo [Client 빌드] 경량 데스크톱 앱...
    py -m PyInstaller client.spec --noconfirm --clean
    echo.
    echo  완료: dist\StockScreenerPro\StockScreenerPro.exe
    echo  배포 시 client_config.json의 server_url을 실서버 주소로 변경하세요.
) else (
    echo.
    echo [Server 빌드] 전체 서버 앱...
    py -m PyInstaller screener_pro.spec --noconfirm --clean
    echo.
    echo  완료: dist\StockScreenerPro\StockScreenerPro.exe
)

echo.
pause
