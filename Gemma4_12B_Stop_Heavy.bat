@echo off
setlocal

cd /d "%~dp0"

set OLLAMA_URL=http://127.0.0.1:11434
set COMFYUI_PORT=8188
set GEMMA_MODEL=gemma4:12b

echo Releasing ComfyUI model memory...
curl -s -X POST http://127.0.0.1:%COMFYUI_PORT%/free -H "Content-Type: application/json" -d "{\"unload_models\":true,\"free_memory\":true}" >nul 2>nul

echo Stopping ComfyUI if it is running...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%COMFYUI_PORT%" ^| findstr "LISTENING"') do (
  taskkill /PID %%a /F >nul 2>nul
)

echo Unloading Gemma from Ollama memory...
curl -s %OLLAMA_URL%/api/generate -H "Content-Type: application/json" -d "{\"model\":\"%GEMMA_MODEL%\",\"prompt\":\"\",\"keep_alive\":0}" >nul 2>nul

echo Done. The Web UI can stay open.
pause
