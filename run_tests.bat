@echo off
cd /d "%~dp0"
title Gemini Live AI Call Agent - Test Suite
echo ========================================================
echo  Running AI Call Agent Test Suite
echo ========================================================
echo.
set PYTHONPATH=%~dp0
".venv\Scripts\python.exe" -m pytest tests/
pause
