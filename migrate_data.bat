@echo off
title Bhumijo System - import your existing records
cd /d "%~dp0"
echo ============================================================
echo   Importing your records into the new database
echo.
echo   Your existing files in Tracker\proposal_backups are opened
echo   READ-ONLY. Nothing there is changed, moved or deleted.
echo ============================================================
echo.
python -m backend.migrate --reset
echo.
echo If it said "verified", every record made it across.
echo Anything needing a human eye is listed in data\migration_review_*.csv
pause
