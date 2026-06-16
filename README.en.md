# Gemma 4 12B Local Web UI

[日本語](README.ja.md) / [English](README.en.md)

Gemma 4 12B Local Web UI is a lightweight browser UI for running local Ollama models such as Gemma 4 12B. It is designed for students and classrooms: no API key is required for basic chat, image input, web search, weather lookup, or local-folder coding workflows.

## Installation Approach

The current distribution uses lightweight launch scripts:

- Mac: `.command` files
- Windows: `.bat` / `.ps1` files

Full installers are possible later:

- Mac: signed `.pkg` or `.dmg`
- Windows: `.msi` or Inno Setup installer

For classroom use, the current script-based setup is simpler to maintain. Ollama and Python are still required, but model downloads can be started from the Settings screen.

## Features

- Local chat with Gemma 4 12B through Ollama
- Japanese / English UI language switch in Settings
- Image input from file picker or clipboard paste
- Web search context using DuckDuckGo HTML search
- Current and weekly weather lookup using Open-Meteo
- Codex-like folders and chats in the left sidebar
- Local folder access for generating and saving code
- Step-by-step code generation: plan, generate files, save, validate, repair
- Streaming display and stop button while generating
- Response mode: Auto / Fast / Standard / Quality
- Reasoning effort: Auto / Light / Standard / Deep
- Local instant answers for current time, date, and weekday
- Short casual chats can route to a lightweight model
- Model downloads from the Settings screen, without typing `ollama pull`
- Optional ComfyUI image generation from chat

## Requirements

- Python 3.10 or later
- Ollama
- Gemma 4 12B model
- Disk space: usually 10GB or more

The first model download can be several GB. On school networks, it may take time.

After launching the app, open `Settings` and use `Download models` to install supported models.

## Quick Start on Mac

1. Install [Ollama](https://ollama.com/download).
2. Open this folder.
3. Run the setup script:

```sh
./scripts/setup-mac.sh
```

4. Start the app:

```sh
./Start_Mac.command
```

You can also double-click `Start_Mac.command`.

If Terminal opens in your home directory, move to this folder first:

```sh
cd ~/Documents/desktop/Gemma4_12B
./Gemma4_12B_全部起動.command
```

## Quick Start on Windows

1. Install [Python](https://www.python.org/downloads/).
   - Enable `Add python.exe to PATH` during installation.
2. Install [Ollama](https://ollama.com/download).
3. Open PowerShell in this folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
```

4. Double-click `Start_Windows.bat`.

## App URL

After starting the app, open:

```text
http://127.0.0.1:54876
```

The Mac launcher opens Safari. Windows uses the default browser.

## Basic Usage

Type a message in the input field at the bottom and send it.

Send controls:

- `↑` button: send
- `■` button: stop generation
- `Cmd + Enter`: send on Mac
- `Ctrl + Enter`: send on Windows
- `Enter`: newline
- `Shift + Enter`: newline

You can enable `Enter to send` in Settings. IME confirmation will not send the message.

## Models

The app can use separate Ollama models for chat, coding, and translation. You can choose models in Settings or from the composer model selector.

Recommended choices:

- Chat: Gemma 4 12B
- Fast chat / translation: Qwen 2.5 3B
- Folder-based coding: Gemma 4 Coder 12B Q4

| Task | Default | Environment variable |
| --- | --- | --- |
| Chat | `gemma4:12b` | `GEMMA_MODEL` |
| Coding | same as `GEMMA_MODEL` | `GEMMA_CODING_MODEL` |
| Translation | lightweight candidate automatically selected | `GEMMA_TRANSLATION_MODEL` |

To use the coding model from the UI:

1. Open `Settings`.
2. Use `Download models` to install `Gemma 4 Coder 12B Q4`.
3. Select it in `Coding model`.

## Weather

Questions such as `today's weather in Tokyo` or `weekly weather in Niigata` use Open-Meteo directly. If no place is written, the app uses `GEMMA_WEATHER_LOCATION`, or Tokyo by default.

## Local Folder Coding

Create a folder in the left sidebar, open its folder settings, and choose a local folder. Then ask the chat to create or edit files.

Examples:

```text
Create a simple web Tetris game in this folder.
Make index.html easier to read.
Make this CSS responsive for mobile.
```

For folder work, the app asks the coding model to generate file content, saves files, validates basic syntax, and tries automatic repair when possible.

For small requests containing words like `simple`, `small`, or `minimal`, the app may skip planning and generate a single `index.html` quickly. More complex requests use Gemma 4 or the Coder model.

Generated HTML files include a `Preview` button in the chat.

## ComfyUI Image Generation

ComfyUI is not included in this repository. This keeps the GitHub repository small and avoids bundling large external projects or model files.

If a `ComfyUI/` folder already exists inside this project folder, you can start everything together.

Mac:

```sh
./Gemma4_12B_全部起動.command
```

Windows:

```bat
Gemma4_12B_All_Start.bat
```

Example prompts:

```text
Generate an image of a red apple.
image generation: rainy Tokyo alley, cinematic light, 512x512
```

Optional parameters:

- `512x512`
- `steps=20`
- `seed=123`

## Troubleshooting

### Python is not found

On Windows, make sure `Add python.exe to PATH` was enabled during Python installation.

### Ollama is not found

Install Ollama and launch the Ollama app once.

### First response is slow

The first response may be slow because the model has to load into memory. Later responses can be faster.

### The computer becomes slow

Image generation and large code generation can be heavy. Stop heavy processes with:

Mac:

```sh
./Gemma4_12B_重い処理を停止.command
```

Windows:

```bat
Gemma4_12B_Stop_Heavy.bat
```

## Developer Notes

Run only the Web UI:

```sh
python3 server.py --host 127.0.0.1 --port 54876
```

Check setup:

```sh
./scripts/check.sh
```

Ask once from CLI:

```sh
./scripts/ask.sh "Introduce yourself briefly in English"
```

Main files:

- `server.py`: local HTTP server, Ollama integration, web search, folder read/write
- `web/index.html`: UI
- `web/app.js`: chat, folders, settings, image input
- `web/styles.css`: visual styles
- `scripts/`: setup, checks, helper scripts

## Not Included in GitHub

The following are ignored by `.gitignore`:

- `ComfyUI/`
- Python virtual environments
- Model files
- Generated images
- Caches
- Logs

## License

MIT License
