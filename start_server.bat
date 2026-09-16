@echo off
title Bhumijo System (port 8787)
cd /d "%~dp0"
echo ============================================================
echo   Bhumijo Proposal ^& Grant Tracker
echo.
echo   On this PC:        http://localhost:8787
echo   API documentation: http://localhost:8787/docs
echo.
echo   The address for other devices is written to
echo   data\SERVER_INFO.txt every time this starts.
echo.
echo   Leave this window open. Closing it stops the server.
echo ============================================================
echo.
python -m backend.main
pause
