@echo off
setlocal

cd /d "%~dp0"

if "%GEMMA_APP_VERSION%"=="" set GEMMA_APP_VERSION=0.4.0
if "%GEMMA_MODEL%"=="" set GEMMA_MODEL=gemma4:12b
if "%GEMMA_CODING_MODEL%"=="" set GEMMA_CODING_MODEL=%GEMMA_MODEL%
if "%GEMMA_TRANSLATION_MODEL%"=="" set GEMMA_TRANSLATION_MODEL=auto

echo Starting Gemma 4 12B Web UI...
echo App version: %GEMMA_APP_VERSION%
echo Chat model: %GEMMA_MODEL%
echo Coding model: %GEMMA_CODING_MODEL%
echo Translation model: %GEMMA_TRANSLATION_MODEL%
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
  echo Starting Ollama server...
  start "Ollama" /min ollama serve
  timeout /t 3 >nul
)

start "" "http://127.0.0.1:54876"
python server.py --host 127.0.0.1 --port 54876

pause
