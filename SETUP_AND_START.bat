@echo off
title Bhumijo System - setup and start
cd /d "%~dp0"
color 0F

echo ============================================================
echo   Bhumijo System - setting up and starting
echo.
echo   This does everything in one go. It may take a few minutes
echo   the first time. Leave this window open when it finishes.
echo ============================================================
echo.

REM --- find Python -------------------------------------------------
set PY=
python --version >nul 2>&1 && set PY=python
if "%PY%"=="" ( py --version >nul 2>&1 && set PY=py )
if "%PY%"=="" (
  echo   ERROR: Python was not found on this PC.
  echo   Install it from python.org, tick "Add Python to PATH",
  echo   then run this file again.
  echo.
  pause
  exit /b 1
)
echo [1/4] Using %PY%
%PY% --version
echo.

REM --- dependencies ------------------------------------------------
echo [2/4] Installing what the server needs (this can take a minute)...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo   ERROR: could not install the requirements.
  echo   Check this PC has an internet connection, then run this again.
  echo.
  pause
  exit /b 1
)
echo   done.
echo.

REM --- settings file -----------------------------------------------
if not exist .env copy .env.example .env >nul

REM --- data ---------------------------------------------------------
echo [3/4] Loading your records into the database...
echo   Your files in Tracker\proposal_backups are opened READ-ONLY.
echo   Nothing there is changed.
%PY% -m backend.migrate --reset
if errorlevel 1 (
  echo.
  echo   The import did not finish. Nothing was changed in your
  echo   original files. Send the message above to Claude.
  echo.
  pause
  exit /b 1
)
echo.

REM --- go -----------------------------------------------------------
echo [4/4] Starting the server...
echo.
echo   Open this in your browser:  http://localhost:8787
echo   Your access token is printed just below.
echo.
echo   KEEP THIS WINDOW OPEN. Closing it stops the server.
echo ============================================================
echo.
%PY% -m backend.main
echo.
echo The server has stopped.
pause
