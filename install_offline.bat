@echo off
chcp 65001 > nul
title Offline Package Installer - Airgapped Setup

echo ========================================================
echo   Mermaid to Microsoft Visio Converter
echo   Airgapped / Offline Dependency Installer
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    py -3 --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [HATA] Python bu sistemde bulunamadi. Lutfen Python yukleyin.
        pause
        exit /b 1
    )
    set PYTHON_CMD=py -3
) else (
    set PYTHON_CMD=python
)

echo Python bulundu: %PYTHON_CMD%
echo Paketler yerel 'wheels' klasorunden kuruluyor (Internet GEREKMEZ)...

%PYTHON_CMD% -m pip install --no-index --find-links="%~dp0wheels" -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Kurulum basarisiz oldu. Lutfen hata mesajlarini kontrol ediniz.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [BASARILI] Tum bagimliliklar cevrimdisi olarak kuruldu!
echo Artik 'run.bat' dosyasini calistirabilirsiniz.
echo ========================================================
pause
exit /b 0
