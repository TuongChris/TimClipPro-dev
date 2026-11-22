@echo off
REM Bo cai DAY DU TimClipPro - nhap dup file nay (KHONG can "Run as administrator").
REM Truoc do: GIAI NEN TOAN BO file ZIP ra mot thu muc (vd. Downloads\TimClipPro_CaiDat).
setlocal
title Cai dat TimClipPro
cd /d "%~dp0"
if not exist "%~dp0cai_dat\CaiDat.ps1" (
    echo [DUNG] Khong thay cai_dat\CaiDat.ps1 - hay GIAI NEN TOAN BO file ZIP roi chay lai.
    pause
    exit /b 1
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0cai_dat\CaiDat.ps1"
set "RC=%errorlevel%"
echo.
pause
exit /b %RC%
