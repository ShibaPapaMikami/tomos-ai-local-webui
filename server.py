#!/usr/bin/env python3
from __future__ import annotations

import argparse
from html import unescape
from html.parser import HTMLParser
import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import random
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
MODEL = os.environ.get("GEMMA_MODEL", "gemma4:12b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
DEFAULT_SYSTEM_PROMPT = (
    "あなたは簡潔で有用なアシスタントです。前置きなしで直接答えてください。"
    "詳しい説明を求められない限り、1〜3個の短い箇条書きで回答してください。"
)
IMAGE_PROMPT_SYSTEM = (
    "Convert the user's image request into one concise English Stable Diffusion prompt. "
    "Preserve the exact subject. If the subject is simple, make it explicit and recognizable. "
    "Return only the prompt, with no quotes, no labels, and no explanation."
)
SEARCH_URL = "https://html.duckduckgo.com/html/"
MAX_TREE_FILES = 700
MAX_FILE_BYTES = 120_000
MAX_CONTEXT_CHARS = 80_000
MAX_IMAGES_PER_MESSAGE = 4
MAX_IMAGE_BASE64_CHARS = 12_000_000
COMFYUI_DEFAULT_PREFIX = "Gemma4UI"
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    ".nuxt",
    "node_modules",
    "dist",
    "build",
    "target",
    "vendor",
    ".venv",
    "venv",
}
TEXT_EXTENSIONS = {
    ".bat",
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".lock",
    ".log",
    ".md",
    ".mjs",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".svelte",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def ollama_json(path: str, payload: dict | None = None, timeout: int = 120) -> dict:
    url = f"{OLLAMA_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def comfyui_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{COMFYUI_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def comfyui_binary(path: str, timeout: int = 60) -> tuple[bytes, str]:
    url = f"{COMFYUI_URL}{path}"
    request = urllib.request.Request(url, headers={"Accept": "image/*"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "image/png")
        return response.read(), content_type


def comfyui_free_memory() -> bool:
    try:
        comfyui_json("/free", {"unload_models": True, "free_memory": True}, timeout=10)
        return True
    except Exception:
        return False


class DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_name = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._current = {"title": "", "url": self._clean_url(attrs_dict.get("href", "")), "snippet": ""}
            self._capture = "title"
            self._parts = []
        elif self._current is not None and "result__snippet" in class_name:
            self._capture = "snippet"
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a" and self._current is not None:
            self._current["title"] = self._clean_text(" ".join(self._parts))
            if self._current["title"] and self._current["url"]:
                self.results.append(self._current)
            self._capture = None
            self._parts = []
        elif self._capture == "snippet" and tag in {"a", "div"} and self._current is not None:
            self._current["snippet"] = self._clean_text(" ".join(self._parts))
            self._capture = None
            self._parts = []

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(unescape(value).split())

    @staticmethod
    def _clean_url(value: str) -> str:
        value = unescape(value)
        parsed = urllib.parse.urlparse(value)
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query:
            return query["uddg"][0]
        return value


def search_web(query: str, max_results: int = 4) -> list[dict[str, str]]:
    query = query.strip()
    if not query:
        return []
    max_results = max(1, min(max_results, 8))
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    request = urllib.request.Request(
        SEARCH_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 Gemma4LocalWebUI/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = DuckDuckGoParser()
    parser.feed(html)
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for result in parser.results:
        url = result.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(result)
        if len(deduped) >= max_results:
            break
    return deduped


def build_search_context(results: list[dict[str, str]]) -> str:
    if not results:
        return "Web search was requested, but no search results were found."
    lines = [
        "Web search results follow. Use them as current context. Cite source numbers when relying on them.",
    ]
    for index, result in enumerate(results, start=1):
        lines.append(
            f"[{index}] {result.get('title', '').strip()}\n"
            f"URL: {result.get('url', '').strip()}\n"
            f"Snippet: {result.get('snippet', '').strip()}"
        )
    return "\n\n".join(lines)


def resolve_workspace_root(root: str) -> Path:
    path = Path(root).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError("workspace root must be an existing directory")
    return path


def pick_workspace_folder() -> dict:
    if sys.platform == "darwin":
        script = 'POSIX path of (choose folder with prompt "フォルダーを選択")'
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ValueError((result.stderr or "フォルダー選択がキャンセルされました。").strip())
        folder = result.stdout.strip()
    else:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="フォルダーを選択")
        root.destroy()
        if not folder:
            raise ValueError("フォルダー選択がキャンセルされました。")

    path = resolve_workspace_root(folder)
    return {"root": str(path)}


def resolve_workspace_file(root: str, relative_path: str) -> Path:
    root_path = resolve_workspace_root(root)
    file_path = (root_path / relative_path).resolve()
    if root_path != file_path and root_path not in file_path.parents:
        raise ValueError("path is outside workspace root")
    return file_path


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        sample = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\x00" not in sample


def workspace_tree(root: str) -> dict:
    root_path = resolve_workspace_root(root)
    files: list[dict[str, object]] = []
    skipped = 0
    for current, dirs, filenames in os.walk(root_path):
        dirs[:] = sorted(name for name in dirs if name not in IGNORED_DIRS and not name.startswith(".DS_Store"))
        filenames = sorted(filenames)
        for filename in filenames:
            if filename == ".DS_Store":
                continue
            path = Path(current) / filename
            try:
                info = path.stat()
            except OSError:
                skipped += 1
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            rel = path.relative_to(root_path).as_posix()
            files.append(
                {
                    "path": rel,
                    "size": info.st_size,
                    "text": info.st_size <= MAX_FILE_BYTES and is_probably_text(path),
                }
            )
            if len(files) >= MAX_TREE_FILES:
                skipped += 1
                return {"root": str(root_path), "files": files, "truncated": True, "skipped": skipped}
    return {"root": str(root_path), "files": files, "truncated": False, "skipped": skipped}


def read_workspace_file(root: str, relative_path: str) -> dict:
    path = resolve_workspace_file(root, relative_path)
    if not path.exists() or not path.is_file():
        raise ValueError("file does not exist")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError(f"file is too large to read in UI ({size} bytes)")
    if not is_probably_text(path):
        raise ValueError("file does not look like text")
    return {
        "path": relative_path,
        "size": size,
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


def write_workspace_file(root: str, relative_path: str, content: str) -> dict:
    if not relative_path or relative_path.endswith("/"):
        raise ValueError("relative file path is required")
    path = resolve_workspace_file(root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": path.relative_to(resolve_workspace_root(root)).as_posix(), "size": len(content.encode("utf-8"))}


SCRIPT_RE = re.compile(r"<script(?:\s[^>]*)?>(.*?)</script>", re.IGNORECASE | re.DOTALL)


def node_check(source: str, suffix: str = ".js") -> list[str]:
    if not source.strip():
        return []
    with tempfile.NamedTemporaryFile("w", suffix=suffix, encoding="utf-8", delete=False) as handle:
        handle.write(source)
        temp_path = handle.name
    try:
        result = subprocess.run(
            ["node", "--check", temp_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except FileNotFoundError:
        return []
    except Exception as exc:
        return [f"JavaScript validation failed: {exc}"]
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
    if result.returncode == 0:
        return []
    return [(result.stderr or result.stdout or "JavaScript syntax error").strip()]


def validate_text_content(relative_path: str, content: str) -> list[str]:
    suffix = Path(relative_path).suffix.lower()
    errors: list[str] = []
    if suffix in {".js", ".mjs", ".cjs"}:
        errors.extend(node_check(content, suffix=".js"))
    elif suffix == ".json":
        try:
            json.loads(content)
        except Exception as exc:
            errors.append(f"JSON parse error: {exc}")
    elif suffix == ".html":
        if "<html" not in content.lower() and "<!doctype html" not in content.lower():
            errors.append("HTML document is missing <html> or <!doctype html>.")
        if content.lower().count("<canvas") > content.lower().count("</canvas>"):
            errors.append("HTML has an unclosed <canvas> tag.")
        for index, script in enumerate(SCRIPT_RE.findall(content), start=1):
            errors.extend(f"script {index}: {error}" for error in node_check(script, suffix=".js"))
    elif suffix == ".css":
        if content.count("{") != content.count("}"):
            errors.append("CSS brace count does not match.")
    return errors


def validate_workspace_files(root: str, files: list[object]) -> dict:
    root_path = resolve_workspace_root(root)
    results: list[dict[str, object]] = []
    ok = True
    for item in files:
        relative_path = str(item.get("path", "") if isinstance(item, dict) else item)
        if not relative_path:
            continue
        try:
            file_data = read_workspace_file(str(root_path), relative_path)
            errors = validate_text_content(relative_path, file_data["content"])
        except Exception as exc:
            errors = [str(exc)]
        if errors:
            ok = False
        results.append({"path": relative_path, "ok": len(errors) == 0, "errors": errors})
    return {"ok": ok, "results": results}


def build_workspace_context(workspace: dict) -> str:
    root = str(workspace.get("root", "")).strip()
    selected = workspace.get("files", [])
    if not root or not isinstance(selected, list):
        return ""
    root_path = resolve_workspace_root(root)
    parts = [
        f"Local workspace root: {root_path}",
        "Use the selected local files as coding context.",
        (
            "When the user asks to create or edit files, provide complete file contents in fenced code blocks "
            "and name the target relative path. Do not claim that file saving is impossible; this UI can save "
            "explicit file contents into the selected local folder. Put the target relative path immediately "
            "before each code block, for example `index.html`. For small browser games and demos, prefer one "
            "complete self-contained `index.html` with embedded CSS and JavaScript unless the user asks for "
            "multiple files."
        ),
    ]
    used = sum(len(part) for part in parts)
    for relative_path in selected[:16]:
        rel = str(relative_path)
        try:
            file_data = read_workspace_file(str(root_path), rel)
        except Exception as exc:
            parts.append(f"\n--- FILE: {rel} ---\n[Could not read: {exc}]")
            continue
        content = file_data["content"]
        remaining = MAX_CONTEXT_CHARS - used
        if remaining <= 0:
            parts.append("\n[Workspace context truncated.]")
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n[File truncated for context.]"
        block = f"\n--- FILE: {rel} ---\n{content}"
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def object_choice(object_info: dict, node: str, field: str, fallback: str) -> list[str]:
    try:
        values = object_info[node]["input"]["required"][field][0]
    except (KeyError, IndexError, TypeError):
        return [fallback] if fallback else []
    if isinstance(values, list):
        return [str(value) for value in values]
    return [str(values)]


def comfyui_status_payload() -> dict:
    try:
        object_info = comfyui_json("/object_info", timeout=5)
        checkpoints = object_choice(object_info, "CheckpointLoaderSimple", "ckpt_name", "")
        samplers = object_choice(object_info, "KSampler", "sampler_name", "euler")
        schedulers = object_choice(object_info, "KSampler", "scheduler", "normal")
        return {
            "ok": True,
            "url": COMFYUI_URL,
            "checkpoints": checkpoints,
            "samplers": samplers,
            "schedulers": schedulers,
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": COMFYUI_URL,
            "checkpoints": [],
            "samplers": [],
            "schedulers": [],
            "error": str(exc),
        }


def clamp_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def clamp_float(value: object, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def multiple_of_eight(value: int) -> int:
    return max(64, min(2048, round(value / 8) * 8))


def pick_default_choice(choices: list[str], preferred: str) -> str:
    if preferred in choices:
        return preferred
    return choices[0] if choices else preferred


def fallback_image_prompt(prompt: str) -> str:
    replacements = {
        "リンゴ": "a single realistic red apple",
        "りんご": "a single realistic red apple",
        "林檎": "a single realistic red apple",
        "猫": "a cute cat",
        "犬": "a cute dog",
        "人物": "a person",
        "風景": "a landscape",
        "写真": "photo",
        "画像": "image",
    }
    converted = prompt
    for source, target in replacements.items():
        converted = converted.replace(source, target)
    if converted != prompt:
        return f"{converted}, centered subject, clear composition, high quality photo"
    return prompt


def enhance_image_prompt(prompt: str) -> str:
    prompt = prompt.strip()
    if not prompt:
        return prompt
    try:
        response = ollama_json(
            "/api/chat",
            payload={
                "model": MODEL,
                "stream": False,
                "think": False,
                "messages": [
                    {"role": "system", "content": IMAGE_PROMPT_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "num_predict": 80,
                    "num_ctx": 1024,
                },
            },
            timeout=90,
        )
        enhanced = str(response.get("message", {}).get("content", "")).strip()
        enhanced = enhanced.strip("`\"' \n")
        if enhanced:
            return enhanced[:800]
    except Exception:
        pass
    return fallback_image_prompt(prompt)[:800]


def build_comfyui_workflow(body: dict, status: dict) -> tuple[dict, dict]:
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("プロンプトを入力してください。")

    checkpoints = status.get("checkpoints", [])
    if not checkpoints:
        raise ValueError("ComfyUIにチェックポイントモデルが見つかりません。ComfyUI側でSDXLなどのモデルを入れてください。")

    samplers = status.get("samplers", []) or ["euler"]
    schedulers = status.get("schedulers", []) or ["normal"]
    checkpoint = str(body.get("checkpoint", "")).strip() or checkpoints[0]
    if checkpoint not in checkpoints:
        checkpoint = checkpoints[0]
    sampler = pick_default_choice(samplers, str(body.get("sampler", "")).strip() or "euler")
    scheduler = pick_default_choice(schedulers, str(body.get("scheduler", "")).strip() or "normal")
    width = multiple_of_eight(clamp_int(body.get("width"), 512, 64, 2048))
    height = multiple_of_eight(clamp_int(body.get("height"), 512, 64, 2048))
    steps = clamp_int(body.get("steps"), 8, 1, 80)
    cfg = clamp_float(body.get("cfg"), 7.0, 1.0, 20.0)
    seed = clamp_int(body.get("seed"), -1, -1, 2**63 - 1)
    if seed < 0:
        seed = random.randint(0, 2**63 - 1)
    negative = str(body.get("negative", "")).strip()

    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt[:4000], "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative[:4000], "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": COMFYUI_DEFAULT_PREFIX, "images": ["8", 0]},
        },
    }
    meta = {
        "prompt": prompt,
        "originalPrompt": str(body.get("original_prompt", prompt)).strip(),
        "checkpoint": checkpoint,
        "sampler": sampler,
        "scheduler": scheduler,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg": cfg,
        "seed": seed,
    }
    return workflow, meta


def collect_comfyui_images(prompt_id: str, history: dict) -> list[dict[str, str]]:
    item = history.get(prompt_id, {})
    outputs = item.get("outputs", {})
    images: list[dict[str, str]] = []
    if not isinstance(outputs, dict):
        return images
    for output in outputs.values():
        for image in output.get("images", []):
            filename = str(image.get("filename", ""))
            subfolder = str(image.get("subfolder", ""))
            image_type = str(image.get("type", "output"))
            if not filename:
                continue
            query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
            images.append(
                {
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": image_type,
                    "url": f"/api/image/view?{query}",
                }
            )
    return images


def generate_comfyui_image(body: dict) -> dict:
    status = comfyui_status_payload()
    if not status.get("ok"):
        raise RuntimeError(f"ComfyUIに接続できません: {status.get('error', 'offline')}")
    prepared_body = dict(body)
    raw_prompt = str(prepared_body.get("prompt", "")).strip()
    if bool(prepared_body.get("enhance_prompt", True)):
        prepared_body["original_prompt"] = raw_prompt
        prepared_body["prompt"] = enhance_image_prompt(raw_prompt)
    workflow, meta = build_comfyui_workflow(prepared_body, status)
    queued = comfyui_json("/prompt", {"prompt": workflow, "client_id": str(uuid.uuid4())}, timeout=10)
    prompt_id = str(queued.get("prompt_id", ""))
    if not prompt_id:
        raise RuntimeError("ComfyUIがprompt_idを返しませんでした。")

    timeout_seconds = clamp_int(body.get("timeout"), 600, 30, 1800)
    deadline = time.time() + timeout_seconds
    history_path = f"/history/{urllib.parse.quote(prompt_id)}"
    while time.time() < deadline:
        history = comfyui_json(history_path, timeout=10)
        if prompt_id in history:
            images = collect_comfyui_images(prompt_id, history)
            if images:
                if bool(body.get("free_after_generate", True)):
                    meta["freedMemory"] = comfyui_free_memory()
                return {"prompt_id": prompt_id, "images": images, "meta": meta}
            raise RuntimeError("ComfyUIの履歴に画像がありません。ワークフローまたはモデルを確認してください。")
        time.sleep(1)
    raise TimeoutError(f"ComfyUIの生成が{timeout_seconds}秒以内に完了しませんでした。")


def sanitize_chat_messages(messages: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = str(message.get("content", ""))
        item: dict[str, object] = {"role": role, "content": content}
        images = message.get("images")
        if isinstance(images, list):
            safe_images = []
            for image in images[:MAX_IMAGES_PER_MESSAGE]:
                if not isinstance(image, str):
                    continue
                if len(image) > MAX_IMAGE_BASE64_CHARS:
                    continue
                safe_images.append(image)
            if safe_images:
                item["images"] = safe_images
        cleaned.append(item)
    return cleaned


def health_payload() -> dict:
    try:
        version = ollama_json("/api/version", timeout=3).get("version", "unknown")
        tags = ollama_json("/api/tags", timeout=3).get("models", [])
        installed = any(item.get("name") == MODEL for item in tags)
        return {
            "ok": True,
            "ollama": "running",
            "version": version,
            "model": MODEL,
            "modelInstalled": installed,
        }
    except Exception as exc:
        return {
            "ok": False,
            "ollama": "offline",
            "model": MODEL,
            "modelInstalled": False,
            "error": str(exc),
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "GemmaWebUI/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            payload = health_payload()
            json_response(self, 200 if payload["ok"] else 503, payload)
            return
        if parsed.path == "/api/image/status":
            payload = comfyui_status_payload()
            json_response(self, 200 if payload["ok"] else 503, payload)
            return
        if parsed.path == "/api/image/view":
            self.handle_image_view(parsed.query)
            return

        path = parsed.path
        if path == "/":
            file_path = WEB_ROOT / "index.html"
        else:
            file_path = (WEB_ROOT / path.lstrip("/")).resolve()
            if not str(file_path).startswith(str(WEB_ROOT.resolve())):
                self.send_error(403)
                return

        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path == "/api/search":
            self.handle_search()
            return
        if self.path == "/api/image/generate":
            self.handle_image_generate()
            return
        if self.path.startswith("/api/workspace/"):
            self.handle_workspace()
            return
        if self.path != "/api/chat":
            self.send_error(404)
            return

        try:
            body = read_json_body(self)
            messages = body.get("messages", [])
            system_prompt = body.get("system", DEFAULT_SYSTEM_PROMPT)
            if not messages or not isinstance(messages, list):
                json_response(self, 400, {"ok": False, "error": "messages must be a non-empty list"})
                return
            history_turns = max(1, min(int(body.get("history_turns", 4)), 20))
            recent_messages = sanitize_chat_messages(messages[-(history_turns * 2) :])
            search_results: list[dict[str, str]] = []
            search_error = ""
            if bool(body.get("web_search", False)):
                query = str(body.get("search_query") or messages[-1].get("content", ""))
                try:
                    search_results = search_web(query, int(body.get("search_results", 4)))
                except Exception as exc:
                    search_error = str(exc)

            prompt_messages = [{"role": "system", "content": system_prompt}]
            if body.get("web_search", False):
                search_context = build_search_context(search_results)
                if search_error:
                    search_context += f"\n\nSearch error: {search_error}"
                prompt_messages.append({"role": "system", "content": search_context})
            if body.get("workspace"):
                try:
                    workspace_context = build_workspace_context(body.get("workspace", {}))
                    if workspace_context:
                        prompt_messages.append({"role": "system", "content": workspace_context})
                except Exception as exc:
                    prompt_messages.append({"role": "system", "content": f"Workspace context error: {exc}"})
            prompt_messages.extend(recent_messages)

            payload = {
                "model": body.get("model") or MODEL,
                "stream": False,
                "think": bool(body.get("think", False)),
                "keep_alive": body.get("keep_alive", "5m"),
                "messages": prompt_messages,
                "options": {
                    "temperature": float(body.get("temperature", 0.7)),
                    "top_p": float(body.get("top_p", 0.9)),
                    "top_k": int(body.get("top_k", 40)),
                    "num_predict": max(16, min(int(body.get("num_predict", 96)), 8192)),
                    "num_ctx": max(512, min(int(body.get("num_ctx", 2048)), 32768)),
                },
            }
            response = ollama_json("/api/chat", payload=payload, timeout=600)
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "message": response.get("message", {}),
                    "model": response.get("model", payload["model"]),
                    "done": response.get("done", True),
                    "search": {
                        "enabled": bool(body.get("web_search", False)),
                        "results": search_results,
                        "error": search_error,
                    },
                },
            )
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            json_response(self, exc.code, {"ok": False, "error": error_body})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_image_generate(self) -> None:
        try:
            body = read_json_body(self)
            result = generate_comfyui_image(body)
            json_response(self, 200, {"ok": True, **result})
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            json_response(self, exc.code, {"ok": False, "error": error_body})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_image_view(self, query: str) -> None:
        try:
            body, content_type = comfyui_binary(f"/view?{query}", timeout=60)
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            json_response(self, 502, {"ok": False, "error": str(exc)})

    def handle_search(self) -> None:
        try:
            body = read_json_body(self)
            query = str(body.get("query", ""))
            results = search_web(query, int(body.get("max_results", 4)))
            json_response(self, 200, {"ok": True, "query": query, "results": results})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_workspace(self) -> None:
        try:
            body = read_json_body(self)
            if self.path == "/api/workspace/tree":
                json_response(self, 200, {"ok": True, **workspace_tree(str(body.get("root", "")))})
            elif self.path == "/api/workspace/pick":
                json_response(self, 200, {"ok": True, **pick_workspace_folder()})
            elif self.path == "/api/workspace/read":
                json_response(
                    self,
                    200,
                    {"ok": True, **read_workspace_file(str(body.get("root", "")), str(body.get("path", "")))},
                )
            elif self.path == "/api/workspace/write":
                result = write_workspace_file(
                    str(body.get("root", "")),
                    str(body.get("path", "")),
                    str(body.get("content", "")),
                )
                json_response(self, 200, {"ok": True, **result})
            elif self.path == "/api/workspace/validate":
                result = validate_workspace_files(str(body.get("root", "")), body.get("files", []))
                json_response(self, 200, result)
            else:
                self.send_error(404)
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Gemma 4 12B Web UI")
    parser.add_argument("--host", default=os.environ.get("GEMMA_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GEMMA_WEB_PORT", "54876")))
    parser.add_argument("--open", action="store_true", help="Open the Web UI in the default browser")
    args = parser.parse_args()

    address = (args.host, args.port)
    httpd = ThreadingHTTPServer(address, Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Gemma 4 12B Web UI: {url}")
    print(f"Ollama: {OLLAMA_URL}")
    print(f"ComfyUI: {COMFYUI_URL}")
    print(f"Model: {MODEL}")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")


if __name__ == "__main__":
    main()
