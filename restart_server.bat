@echo off
REM Stops whatever is serving port 8787 and starts a fresh server.
REM
REM Closing the console window does not always kill the Python process behind
REM it - it can keep holding the port, so the next start fails with
REM [Errno 10048] and you end up with an old version still serving.
REM
REM This targets ONLY the process listening on this system's port. It will not
REM touch the old Proposal Tracker on 8585, the HR dashboard on 8000, or any
REM other Python you have running.

title Bhumijo System - restart
cd /d "%~dp0"

set PORT=8787

echo ============================================================
echo   Restarting the Bhumijo System (port %PORT%)
echo ============================================================
echo.

echo Looking for anything listening on port %PORT%...
powershell -NoProfile -Command ^
  "$c = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue;" ^
  "if ($c) { $c | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {" ^
  "  $p = Get-Process -Id $_ -ErrorAction SilentlyContinue;" ^
  "  if ($p) { Write-Host ('  stopping ' + $p.ProcessName + ' (pid ' + $p.Id + ')');" ^
  "            Stop-Process -Id $p.Id -Force } } }" ^
  "else { Write-Host '  nothing was listening - good' }"

echo.
echo Waiting for the port to be released...
timeout /t 3 /nobreak >nul

set PY=
python --version >nul 2>&1 && set PY=python
if "%PY%"=="" ( py --version >nul 2>&1 && set PY=py )
if "%PY%"=="" (
  echo   ERROR: Python was not found.
  pause
  exit /b 1
)

%PY% tools\port_free.py
if errorlevel 1 (
  echo.
  echo   The port is still in use. Something else is holding it.
  echo   Restart the PC and try again.
  echo.
  pause
  exit /b 1
)

echo.
echo Starting the server...
echo   Open http://localhost:8787
echo   KEEP THIS WINDOW OPEN. Closing it stops the server.
echo ============================================================
echo.
%PY% -m backend.main
echo.
echo The server has stopped.
pause
