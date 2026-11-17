@echo off
setlocal
chcp 65001 >nul
title Frodo - Model Downloader (Gemma 4 + EmbeddingGemma 2)

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo =======================================================================
echo   🧙 FRODO: АВТОНОМНЫЙ ВЫСОКОСКОРОСТНОЙ ЗАГРУЗЧИК МОДЕЛЕЙ
echo   Целевая папка: %SCRIPT_DIR%models\
echo =======================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python не найден в переменной PATH!
    echo Установите Python 3.10+ или добавьте его в системный PATH.
    pause
    exit /b 1
)

python server\src\model_downloader.py %*

echo.
echo =======================================================================
echo   Работа загрузчика завершена.
echo =======================================================================
pause
