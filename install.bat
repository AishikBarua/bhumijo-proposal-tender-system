@echo off
title Bhumijo System - one-time setup
cd /d "%~dp0"
echo ============================================================
echo   Bhumijo System - one-time setup
echo ============================================================
echo.
echo [1/4] Checking Python...
python --version || (echo   Python not found. Install it from python.org, then run this again. & pause & exit /b 1)
echo.
echo [2/4] Installing what the server needs...
python -m pip install -r requirements.txt || (echo   Install failed. & pause & exit /b 1)
echo.
echo [3/4] Downloading Chart.js so the charts work offline...
python tools\vendor_chartjs.py
echo.
echo [4/4] Setting up your settings file...
if not exist .env (
  copy .env.example .env >nul
  echo   Created .env - open it in Notepad to set the backup folder.
) else (
  echo   .env already exists, leaving it alone.
)
echo.
echo ============================================================
echo   Setup done. Next:
echo     1. migrate_data.bat   - copy your records into the database
echo     2. start_server.bat   - start the system
echo ============================================================
pause
