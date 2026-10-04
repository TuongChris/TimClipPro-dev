@echo off
cd /d "%~dp0"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY py -3.12 --version >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY exit /b 1

REM Link Google Sheet KHONG nam trong ma nguon (repo cong khai). Lay theo thu tu:
REM   1) bien moi truong SHEET_LINK (giong ChayMayPhu.bat; dat trong Task Scheduler);
REM   2) dong dau cua data\giam_sat_sheet.txt (thu muc data\ khong vao git).
REM Khong co ca hai thi Giam sat van chay va xuat CSV, nhung KHONG ghi Google Sheets.
if not defined SHEET_LINK if exist "data\giam_sat_sheet.txt" set /p SHEET_LINK=<"data\giam_sat_sheet.txt"

if defined SHEET_LINK (
    %PY% cli.py watch --log --sheet "%SHEET_LINK%"
) else (
    echo [GiamSat] Chua cau hinh link Google Sheet - chi xuat CSV, khong ghi Google Sheets.
    echo [GiamSat] Dat bien SHEET_LINK hoac ghi link vao data\giam_sat_sheet.txt.
    %PY% cli.py watch --log
)
set "EXIT_CODE=%errorlevel%"
exit /b %EXIT_CODE%
