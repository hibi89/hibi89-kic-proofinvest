@echo off
setlocal
cd /d "%~dp0"
python -B -m scripts.local_ui_launcher --enable-local-review %*
exit /b %ERRORLEVEL%
