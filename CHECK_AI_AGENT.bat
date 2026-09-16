@echo off
REM Checks whether the AI Agent can actually work, and says what is missing.
REM Run this after adding your API key to .env.
title Bhumijo - can the AI Agent work?
cd /d "%~dp0"
set PY=
python --version >nul 2>&1 && set PY=python
if "%PY%"=="" ( py --version >nul 2>&1 && set PY=py )
if "%PY%"=="" ( echo Python not found. & pause & exit /b 1 )
%PY% tools\check_agent.py
pause
