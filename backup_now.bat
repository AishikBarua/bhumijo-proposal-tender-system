@echo off
title Bhumijo System - backup
cd /d "%~dp0"
python -m backend.jobs.backup
pause
