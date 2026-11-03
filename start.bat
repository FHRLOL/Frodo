@echo off
setlocal
cd /d "%~dp0"

echo ======================================================================
echo    FRODO AI MENTOR: Starting System (Gemma 4 + EmbeddingGemma 2)
echo    UI: Holad Design System (LTI 1.1 + Moodle Integration)
echo ======================================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.10+ and add it to your PATH environment variable.
    pause
    exit /b 1
)

python run.py
if errorlevel 1 (
    echo.
    echo [ERROR] Frodo AI Mentor exited with an error.
    pause
)
