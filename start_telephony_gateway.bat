@echo off
cd /d "%~dp0"
title Gemini Live AI Call Agent - Telephony Gateway Server
echo ========================================================
echo  Starting Telephony Gateway (Twilio / SIP Media Streams)
echo ========================================================
echo.
set PYTHONPATH=%~dp0
".venv\Scripts\python.exe" -m agent.telephony.gateway
pause
