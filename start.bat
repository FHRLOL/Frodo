@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ======================================================================
echo    🧙‍♂️ FRODO: Запуск ИИ-наставника (Gemma 4 + EmbeddingGemma 2)
echo    Интерфейс: Holad Design System (LTI 1.1 + Moodle Integration)
echo ======================================================================
echo.

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ОШИБКА] Python не обнаружен в переменной PATH.
    echo Пожалуйста, установите Python 3.10+ и добавьте его в PATH.
    pause
    exit /b 1
)

python run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ОШИБКА] Сбой при выполнении Frodo AI Mentor.
    pause
)
