@echo off
setlocal

cd /d "%~dp0"

set WEB_HOST=127.0.0.1
set WEB_PORT=54876
set WEB_URL=http://%WEB_HOST%:%WEB_PORT%

echo Starting Gemma 4 12B + ComfyUI...
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
