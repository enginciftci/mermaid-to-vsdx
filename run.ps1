# Mermaid to Microsoft Visio Converter Launcher (PowerShell)
$ErrorActionPreference = "Continue"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Mermaid to Microsoft Visio (.vsdx) Converter" -ForegroundColor Cyan
Write-Host "  Windows 11 Professional Desktop Application" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$pythonCmd = $null
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
}

if (-not $pythonCmd) {
    Write-Host "[HATA] Python bu sistemde bulunamadi. Lutfen Python 3.10+ yukleyin." -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Python bulundu: $pythonCmd" -ForegroundColor Green
Write-Host "Uygulama baslatiliyor..." -ForegroundColor Yellow

& $pythonCmd "$PSScriptRoot\main.py" $args
