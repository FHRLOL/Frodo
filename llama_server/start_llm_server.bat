@echo off
setlocal
chcp 65001 >nul
title Frodo Local LLM Server (Gemma 4 E4B)

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set MODEL_PATH=%SCRIPT_DIR%..\models\gemma-4-e4b-it-q4_k_m.gguf
set PORT=8086

echo =================================================================
echo   Starting Frodo LLM Server (Gemma 4 E4B) on port %PORT%
echo   Model: %MODEL_PATH%
echo =================================================================

if not exist "%MODEL_PATH%" (
    echo [WARN] Model not found: %MODEL_PATH%
    echo Please ensure the model file is placed in the models directory.
    pause
    exit /b 1
)

llama-server.exe ^
  -m "%MODEL_PATH%" ^
  --port %PORT% ^
  --host 127.0.0.1 ^
  -ngl 99 ^
  -c 16384 ^
  -np 8 ^
  --cont-batching ^
  --cache-type-k q8_0 ^
  --cache-type-v q8_0 ^
  --threads 8

pause
