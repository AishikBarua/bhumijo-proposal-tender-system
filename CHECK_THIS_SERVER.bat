@echo off
REM Run this ON THE MACHINE you want to move Bhumijo to, before copying anything.
REM It only looks and reports - it changes nothing at all.
REM
REM It tells you whether that machine can host Bhumijo: Python version, whether
REM port 8787 is free, whether the database would sit on a local disk, whether
REM it can reach the internet, and its address on the office network.

title Can this machine host Bhumijo?
cd /d "%~dp0"

set PY=
python --version >nul 2>&1 && set PY=python
if "%PY%"=="" ( py --version >nul 2>&1 && set PY=py )
if "%PY%"=="" (
  echo.
  echo ============================================================
  echo   Python is NOT installed on this machine.
  echo.
  echo   That is the first thing to fix. Get it from python.org,
  echo   and during setup tick "Add Python to PATH".
  echo.
  echo   Then run this file again.
  echo ============================================================
  echo.
  pause
  exit /b 1
)

%PY% tools\server_check.py

echo.
echo Press any key to close. Copy the text above and send it to Claude.
pause >nul
