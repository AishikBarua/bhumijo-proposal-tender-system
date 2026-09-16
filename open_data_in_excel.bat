@echo off
REM Exports everything in the database to spreadsheets you can open, then
REM opens the folder they were written to.
REM
REM bhumijo.db is a binary database file - Windows has no application for it,
REM so double-clicking it does nothing. This is how to see the raw data.
REM
REM It only READS the database. Safe to run while the server is running and
REM people are using the tracker.

title Bhumijo System - export data to Excel
cd /d "%~dp0"

set PY=
python --version >nul 2>&1 && set PY=python
if "%PY%"=="" ( py --version >nul 2>&1 && set PY=py )
if "%PY%"=="" (
  echo   ERROR: Python was not found on this PC.
  pause
  exit /b 1
)

echo ============================================================
echo   Exporting your data to spreadsheets
echo ============================================================
echo.

%PY% tools\export_data.py
if errorlevel 1 (
  echo.
  pause
  exit /b 1
)

echo.
echo Opening the folder...
start "" "%~dp0data\export"
echo.
pause
