@echo off
REM Makes the Bhumijo System (port 8787) start automatically and silently
REM every time you log in to Windows. No admin rights needed - this uses your
REM personal Startup folder.
REM
REM This is a SEPARATE entry from the old Proposal Tracker server on 8585
REM (install_proposal_autostart.bat) and from the HR & Vendor Dashboard on
REM 8000. Installing this does not touch either of them - all three can start
REM at login, on their three different ports, without interfering.

title Bhumijo System - install auto-start
cd /d "%~dp0"

set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set TARGET=%STARTUP_DIR%\Bhumijo_System_AutoStart.vbs

echo ============================================================
echo   Installing auto-start for the Bhumijo System (port 8787)
echo ============================================================
echo.

REM --- check Python is there before promising anything ---------------
set PY=
python --version >nul 2>&1 && set PY=python
if "%PY%"=="" ( py --version >nul 2>&1 && set PY=py )
if "%PY%"=="" (
  echo   ERROR: Python was not found on this PC.
  echo   Auto-start would fail silently at every login, so nothing was
  echo   installed. Install Python from python.org first.
  echo.
  pause
  exit /b 1
)

REM --- check the data has been imported ------------------------------
if not exist "data\bhumijo.db" (
  echo   The database does not exist yet.
  echo.
  echo   Run SETUP_AND_START.bat once first - it imports your records.
  echo   Auto-start deliberately never imports data, so setting it up
  echo   before the first import would just start an empty system.
  echo.
  pause
  exit /b 1
)

echo Writing the startup entry...
(
  echo Set objShell = CreateObject^("WScript.Shell"^)
  echo objShell.Run "wscript.exe //nologo ""%~dp0run_hidden.vbs""", 0, False
) > "%TARGET%"

if exist "%TARGET%" (
  echo.
  echo   Done. The Bhumijo System will now start automatically and
  echo   silently every time you log in to this PC - no window appears.
  echo.
  echo   Because nothing appears on screen, read the address and the
  echo   access token from:
  echo       %~dp0data\SERVER_INFO.txt
  echo   It is rewritten every time the server starts.
  echo.
  echo   If it ever seems not to be running, check:
  echo       data\logs\autostart.log       - starts, stops and restarts
  echo       data\logs\server_console.log  - what the server printed
  echo.
  echo   To undo this, run uninstall_autostart.bat.
  echo.
  echo ------------------------------------------------------------
  echo   Starting it right now as well...

  REM Only if nothing is already using the port - otherwise this would
  REM start a second copy that fights the first one for it.
  %PY% tools\port_free.py >nul 2>&1
  if errorlevel 1 (
    echo   A server is already running on this port, so nothing was
    echo   started. It will start on its own at your next login.
  ) else (
    wscript.exe //nologo "%~dp0run_hidden.vbs"
    echo   Started. Give it a few seconds, then open http://localhost:8787
  )
) else (
  echo.
  echo   Something went wrong - could not write the file to:
  echo   %STARTUP_DIR%
)

echo.
pause
