# TOMOS AI

[日本語](README.ja.md) / [English](README.en.md)

TOMOS AI is a lightweight browser UI for running local Ollama models such as Gemma 4 12B. It is designed for students and classrooms: no API key is required for basic chat, image input, web search, weather lookup, or local-folder coding workflows.

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

For classroom distribution, download the OS-specific ZIP from GitHub Releases.

- Mac: `TOMOS_AI-vX.X.X-mac.zip`
- Windows: `TOMOS_AI-vX.X.X-windows.zip`

Japanese install notes are available in [docs/install-students.ja.md](docs/install-students.ja.md). Release packaging notes are in [docs/github-release-guide.ja.md](docs/github-release-guide.ja.md).

1. Install [Ollama](https://ollama.com/download).
2. Open this folder.
3. Run the setup script:

```sh
./scripts/setup-mac.sh
```

4. Start the app:

```sh
./Gemma4_12B_全部起動.command
```

You can also double-click `Gemma4_12B_全部起動.command`.

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

4. Double-click `Gemma4_12B_All_Start.bat`.

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

## Exporting Training Data

Open Settings and use the Training data section to create training sets for Gemma.

A training set does not immediately rewrite the model. It first stores named corrections and good answer examples, then applies them to a folder as chat-time hints.

When you have enough good examples, export a training file. Think of this file as a notebook of conversations you want Gemma to learn from. Exporting it does not change the model yet. In the next step, clean the file, then use fine-tuning to create a new model.

Basic flow:

1. Create a training set in Settings.
2. Use Correct and learn below a Gemma reply to save the corrected answer.
3. Apply the training set to a folder.
4. Chats in that folder use the saved corrections as hints.
5. Export a training file when you have enough examples.
6. In the next stage, create a new model from that training file.
7. Choose the finished model in Settings > Models, then use it for chats or folders.

The current app directly supports steps 1-5. Steps 6-7 are the next implementation stage, with a goal of running them from the UI without terminal commands.

You can export:

- Current chat
- Current folder
- All chats
- Selected training set

The exported file is a training notebook with one user question and one correct answer per line. In normal use, students do not need to edit it directly.

For developers, it is stored as `JSONL`: a format that lists many conversation examples in a way training tools can read.

```json
{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"..."}],"metadata":{"task":"translation","model":"gemma4:12b"}}
```

Before creating a new model, clean the file by removing empty or failed examples. For now, use this command; a UI action is planned for a later version:

```sh
python3 scripts/standardize_training_data.py gemma4-training-active-YYYYMMDD-HHMMSS.jsonl
```

Keep metadata for filtering or debugging:

```sh
python3 scripts/standardize_training_data.py gemma4-training-active-YYYYMMDD-HHMMSS.jsonl --keep-metadata
```

Start with high-quality examples: successful translations, natural short replies, and code generations that saved and validated correctly.

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

- `server.py`: local HTTP server, Ollama integration, folder read/write, weather and image APIs
- `search_tools.py`: web search fetching, HTML parsing, and search-context generation
- `web/index.html`: UI
- `web/app.js`: app state, event wiring, and module coordination
- `web/messages.js`: chat rendering
- `web/sidebar.js`: folders and chat list
- `web/settings.js`: settings panel and model download UI
- `web/workspace.js`: local folders, saving, previews, and code extraction
- `web/training.js`: training sets, corrections, and training-file export
- `web/search.js`: frontend web-search state, result normalization, and search generation settings
- `web/weather.js`: weather detection, place extraction, and saved browser location
- `web/composer.js`: input box, image attachments, and submit behavior
- `web/styles.css`: visual styles
- `scripts/test-*.js`: regression tests for frontend helpers
- `scripts/test_search_tools.py`: regression tests for server-side search helpers

Recommended checks after changes:

```sh
node scripts/test-router.js && node scripts/test-workspace-helpers.js && node scripts/test-submit-classification.js && node scripts/test-model-selection.js && node scripts/test-training-export.js && node scripts/test-weather-helpers.js && node scripts/test-settings-helpers.js && node scripts/test-search-helpers.js
python3 scripts/test_search_tools.py
python3 -m py_compile server.py search_tools.py scripts/standardize_training_data.py
```

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
