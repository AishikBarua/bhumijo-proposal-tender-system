@echo off
REM Removes the Bhumijo System's auto-start entry (undoes install_autostart.bat).
REM
REM This does not touch the old Proposal Tracker's autostart entry on 8585,
REM or the HR & Vendor Dashboard's on 8000. It also does not stop a server
REM that is running right now - it only stops it starting at your next login.

title Bhumijo System - remove auto-start
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set TARGET=%STARTUP_DIR%\Bhumijo_System_AutoStart.vbs

if exist "%TARGET%" (
  del "%TARGET%"
  echo Auto-start removed. The Bhumijo System will no longer start
  echo automatically when you log in.
  echo.
  echo You can still start it any time with start_server.bat.
  echo.
  echo A server that is already running is NOT stopped by this. To stop it
  echo now, open Task Manager and end the python.exe process, or restart
  echo the PC.
) else (
  echo No auto-start entry was found - nothing to remove.
)
echo.
pause
