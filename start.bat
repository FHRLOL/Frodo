@echo off
setlocal
cd /d "%~dp0"
python run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start Frodo. Please check Python installation.
    pause
)
