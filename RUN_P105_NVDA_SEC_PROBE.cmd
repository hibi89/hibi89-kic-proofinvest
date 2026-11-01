@echo off
setlocal
cd /d "%~dp0"
echo KUODRA P105 - Owner-approved NVIDIA SEC data probe
echo Four official SEC GET requests at most. No data files saved.
python -B -m scripts.p105_authorized_nvda_sec_probe
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo SEC probe not complete. See redacted reason above.
exit /b %RESULT%
