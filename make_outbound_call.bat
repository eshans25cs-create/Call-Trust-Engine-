@echo off
title Gemini Live AI Call Agent - Outbound Call Trigger
echo ========================================================
echo  Trigger Outbound Call via Gemini Live Telephony
echo ========================================================
echo.
set /p DEST_NUMBER="Enter phone number to call (with country code, e.g. +15551234567): "
echo.
echo Calling %DEST_NUMBER%...
"%~dp0.venv\Scripts\python.exe" -m agent.telephony.outbound --to %DEST_NUMBER%
pause
