@echo off
cd /d "%~dp0"
title Gemini Live AI Call Agent - Local Voice Console
echo ========================================================
echo  Starting Real-Time Gemini Live Voice Call Agent
echo ========================================================
echo.
".venv\Scripts\python.exe" "client\test_call.py"
pause
