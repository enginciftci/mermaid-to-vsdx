@echo off
chcp 65001 > nul
title Mermaid to Microsoft Visio Converter

echo ========================================================
echo   Mermaid to Microsoft Visio (.vsdx) Converter
echo   Windows 11 Professional Desktop Application
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

%PYTHON_CMD% -c "import win32com.client, PIL, sv_ttk" >nul 2>&1
if %errorlevel% neq 0 (
    echo Bagimliliklar kuruluyor...
    if exist "%~dp0wheels" (
        %PYTHON_CMD% -m pip install --no-index --find-links="%~dp0wheels" -r "%~dp0requirements.txt" --quiet
    ) else (
        %PYTHON_CMD% -m pip install -r "%~dp0requirements.txt" --quiet
    )
)

echo.
if not "%~1"=="" (
    %PYTHON_CMD% "%~dp0main.py" %*
    exit /b %errorlevel%
)

echo Uygulama baslatiliyor...
start "" %PYTHON_CMD% "%~dp0main.py"
exit /b 0
