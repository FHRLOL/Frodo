@echo off
chcp 65001 >nul
title Frodo Local Embedding Server (EmbeddingGemma 2)

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set MODEL_PATH=%SCRIPT_DIR%..\models\embeddinggemma-2-Q8_0.gguf
set PORT=8085

echo =================================================================
echo   Starting Frodo Local Embedding Server on port %PORT%
echo   Model: %MODEL_PATH%
echo =================================================================

if not exist "%MODEL_PATH%" (
    echo [WARN] Model not found: %MODEL_PATH%
    echo To download weights, run download_models.bat.
    pause
    exit /b 1
)

llama-server.exe ^
  -m "%MODEL_PATH%" ^
  --embedding ^
  --port %PORT% ^
  --host 127.0.0.1 ^
  -ngl 0 ^
  -c 8192 ^
  --threads 8

pause
