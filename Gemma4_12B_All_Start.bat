@echo off
setlocal

cd /d "%~dp0"

set WEB_HOST=127.0.0.1
set WEB_PORT=54876
set WEB_URL=http://%WEB_HOST%:%WEB_PORT%
set GEMMA_APP_VERSION=0.8.196
if "%GEMMA_MODEL%"=="" set GEMMA_MODEL=gemma4:12b
if "%GEMMA_CODING_MODEL%"=="" set GEMMA_CODING_MODEL=%GEMMA_MODEL%
if "%GEMMA_TRANSLATION_MODEL%"=="" set GEMMA_TRANSLATION_MODEL=auto
if "%GEMMA_ASR_MODEL%"=="" set GEMMA_ASR_MODEL=whisper.cpp:tiny
if "%GEMMA_ASR_RUNNER%"=="" set GEMMA_ASR_RUNNER=python scripts/asr_nemotron_runner.py
if "%GEMMA_ASR_WORKER%"=="" set GEMMA_ASR_WORKER=python scripts/asr_nemotron_worker.py
if "%GEMMA_ASR_LANGUAGE%"=="" set GEMMA_ASR_LANGUAGE=ja-JP

echo Starting Gemma 4 12B + ComfyUI...
echo App version: %GEMMA_APP_VERSION%
echo Chat model: %GEMMA_MODEL%
echo Coding model: %GEMMA_CODING_MODEL%
echo Translation model: %GEMMA_TRANSLATION_MODEL%
echo ASR model: %GEMMA_ASR_MODEL%
echo ASR runner: %GEMMA_ASR_RUNNER%
echo ASR worker: %GEMMA_ASR_WORKER%
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not available in PATH.
  pause
  exit /b 1
)

where ollama >nul 2>nul
if errorlevel 1 (
  echo Ollama is not installed or not available in PATH.
  pause
  exit /b 1
)

curl -s http://127.0.0.1:11434/api/version >nul 2>nul
if errorlevel 1 (
  echo Starting Ollama...
  start "Ollama" /min ollama serve
  timeout /t 3 >nul
)

curl -s http://127.0.0.1:8188/object_info >nul 2>nul
if errorlevel 1 (
  if exist "ComfyUI\\.venv\\Scripts\\python.exe" (
    echo Starting ComfyUI...
    pushd ComfyUI
    start "ComfyUI" /min ".venv\\Scripts\\python.exe" main.py --listen 127.0.0.1 --port 8188
    popd
    timeout /t 8 >nul
  ) else (
    echo ComfyUI Windows Python environment is not ready.
    echo Create ComfyUI\\.venv and install ComfyUI\\requirements.txt first.
  )
)

echo Web UI: %WEB_URL%
echo ComfyUI: http://127.0.0.1:8188
echo.

start "" "%WEB_URL%"
python server.py --host %WEB_HOST% --port %WEB_PORT%

pause
