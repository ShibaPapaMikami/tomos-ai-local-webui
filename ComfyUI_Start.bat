@echo off
setlocal

cd /d "%~dp0"

if not exist "ComfyUI\\.venv\\Scripts\\python.exe" (
  echo ComfyUI Python environment is not ready.
  echo On Windows, create ComfyUI\\.venv and install ComfyUI\\requirements.txt first.
  pause
  exit /b 1
)

curl -s http://127.0.0.1:8188/object_info >nul 2>nul
if not errorlevel 1 (
  echo ComfyUI is already running at http://127.0.0.1:8188
  pause
  exit /b 0
)

cd ComfyUI
set PYTORCH_ENABLE_MPS_FALLBACK=1
start "ComfyUI" /min ".venv\\Scripts\\python.exe" main.py --listen 127.0.0.1 --port 8188
cd ..

echo ComfyUI is starting at http://127.0.0.1:8188
pause
