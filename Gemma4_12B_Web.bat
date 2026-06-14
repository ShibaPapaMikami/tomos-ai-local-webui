@echo off
setlocal

cd /d "%~dp0"

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
