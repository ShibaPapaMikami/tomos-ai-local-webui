@echo off
setlocal

cd /d "%~dp0"

set GEMMA_APP_VERSION=0.8.200
if "%GEMMA_MODEL%"=="" set GEMMA_MODEL=gemma4:12b
if "%GEMMA_CODING_MODEL%"=="" set GEMMA_CODING_MODEL=%GEMMA_MODEL%
if "%GEMMA_TRANSLATION_MODEL%"=="" set GEMMA_TRANSLATION_MODEL=auto
if "%GEMMA_ASR_MODEL%"=="" set GEMMA_ASR_MODEL=whisper.cpp:tiny
if "%GEMMA_ASR_RUNNER%"=="" set GEMMA_ASR_RUNNER=python scripts/asr_nemotron_runner.py
if "%GEMMA_ASR_WORKER%"=="" set GEMMA_ASR_WORKER=python scripts/asr_nemotron_worker.py
if "%GEMMA_ASR_LANGUAGE%"=="" set GEMMA_ASR_LANGUAGE=ja-JP

echo Starting Gemma 4 12B Web UI...
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

set OLLAMA_EXE=
for %%I in (ollama.exe) do set "OLLAMA_EXE=%%~$PATH:I"
if "%OLLAMA_EXE%"=="" if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if "%OLLAMA_EXE%"=="" if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
if "%OLLAMA_EXE%"=="" if exist "%ProgramFiles(x86)%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles(x86)%\Ollama\ollama.exe"
if "%OLLAMA_EXE%"=="" (
  echo Ollama is not installed or could not be found.
  echo Install Ollama from https://ollama.com/download, then open Ollama once.
  pause
  exit /b 1
)

curl -s http://127.0.0.1:11434/api/version >nul 2>nul
if errorlevel 1 (
  echo Starting Ollama server...
  start "Ollama" /min "%OLLAMA_EXE%" serve
  timeout /t 3 >nul
)

start "" "http://127.0.0.1:54876"
python server.py --host 127.0.0.1 --port 54876

pause
