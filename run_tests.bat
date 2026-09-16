@echo off
title Bhumijo System - checks
cd /d "%~dp0"
echo === Does the code still follow the folder architecture? ===
python -m backend.tests.test_architecture
echo.
echo === Does it return exactly what the old files hold? ===
python -m backend.tests.test_parity
echo.
echo === Does it behave the way it should? ===
python -m backend.tests.test_behaviour
echo.
echo === Does every link between the screens work? ===
python -m backend.tests.test_navigation
echo.
echo === Is the token typed once and then remembered? ===
python -m backend.tests.test_remember_device
echo.
echo === Office devices in with no token, outsiders still out? ===
python -m backend.tests.test_trusted_network
echo.
echo === Does the no-API Tender Finder work, without calling any API? ===
python -m backend.tests.test_agent_free
pause
