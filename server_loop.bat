@echo off
REM Keeps the server running: starts it, and starts it again if it ever stops.
REM
REM Used internally by run_hidden.vbs. You should not need to run this
REM directly — use start_server.bat if you want a visible window.
REM
REM It deliberately does NOT re-import your data. Autostart must never run
REM the migration: that would wipe the database and rebuild it from the old
REM JSONL files every time you log in, throwing away anything entered since.

cd /d "%~dp0"

set PY=
python --version >nul 2>&1 && set PY=python
if "%PY%"=="" ( py --version >nul 2>&1 && set PY=py )
if "%PY%"=="" (
  echo [%DATE% %TIME%] Python not found - cannot start. >> "data\logs\autostart.log"
  exit /b 1
)

if not exist "data\logs" mkdir "data\logs"

:loop

REM --- is another copy already serving? ------------------------------
REM Without this check a second copy fails to bind and restarts forever,
REM invisibly, because this runs with no window.
%PY% tools\port_free.py >nul 2>&1
if errorlevel 1 (
  echo [%DATE% %TIME%] Port already in use - another server is running. Waiting. >> "data\logs\autostart.log"
  timeout /t 60 /nobreak >nul
  goto loop
)

echo [%DATE% %TIME%] Starting server. >> "data\logs\autostart.log"
%PY% -m backend.main >> "data\logs\server_console.log" 2>&1
echo [%DATE% %TIME%] Server stopped (exit code %ERRORLEVEL%). Restarting in 15s. >> "data\logs\autostart.log"

REM 15 seconds, not 3. If it is failing on startup this stops it from
REM spinning hot and filling the disk with log lines.
timeout /t 15 /nobreak >nul
goto loop
