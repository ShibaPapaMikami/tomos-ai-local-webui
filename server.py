#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
import hashlib
import importlib.util
import ipaddress
import io
import json
import locale
import mimetypes
import os
import platform
import queue
import re
import shutil
import shlex
import socket
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import random
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
import zipfile
import xml.etree.ElementTree as ET

from search_tools import build_search_context, search_web
from agent_reach_adapter import DoctorCache, RouteDecision, run_exa_search, select_route
from pdf_reader import (
    clamp_pdf_page_number,
    extract_image_ocr_text,
    extract_pdf_page_text,
    extract_pdf_text,
    extract_pdf_text_with_mdls,
    extract_pdf_text_with_pdftotext,
    ocr_capabilities,
    pdf_page_count,
    usable_pdf_text,
)
from knowledge_layer import (
    default_db_path,
    index_folder as index_knowledge_folder,
    knowledge_status,
    search_knowledge,
)
from context_core import build_context as build_local_context
from context_core import context_db_path
from context_core import forget_context_record
from context_core import knowledge_result_to_records
from context_core import list_context_records
from context_core import profile as context_profile
from context_core import remember
from context_core import save_context_record
from context_core import update_context_record
from contract_ledger import (
    default_contract_db_path,
    delete_contract,
    extract_contract_candidate,
    list_contracts,
    save_contract,
)
from sarashina_ocr_runner import sarashina_compare_page_payload, sarashina_ocr_status

try:
    import segno
except ImportError:
    segno = None


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
KNOWLEDGE_DB_PATH = default_db_path(ROOT)
CONTEXT_DB_PATH = context_db_path(ROOT)
CONTRACT_DB_PATH = default_contract_db_path(ROOT)
PERSON_PHOTO_DIR = ROOT / "data" / "person-photos"
PERSON_PHOTO_MAX_BYTES = 2 * 1024 * 1024
PERSON_PHOTO_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
APP_VERSION = os.environ.get("GEMMA_APP_VERSION", "0.8.218")
GEMMA_BASE_MODEL = "gemma4:12b"
GEMMA_MLX_MODEL = "gemma4:12b-mlx"
MODEL = os.environ.get("GEMMA_MODEL", GEMMA_MLX_MODEL)
CODING_MODEL = os.environ.get("GEMMA_CODING_MODEL", "")
TRANSLATION_MODEL = os.environ.get("GEMMA_TRANSLATION_MODEL", "")
TRANSLATION_MODEL_CANDIDATES = [
    "qwen2.5:3b",
    "phi3:latest",
    "llama3:latest",
]
CODING_MODEL_CANDIDATES = [
    GEMMA_MLX_MODEL,
    "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M",
]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
MOBILE_PAIRING_TTL_SECONDS = 600
MOBILE_PAIRING_STATE: dict[str, object] = {}
MOBILE_PENDING_IMPORTS: list[dict[str, object]] = []
MOBILE_IMPORT_LOCK = threading.Lock()

SUBPROCESS_OUTPUT_ENCODINGS = tuple(dict.fromkeys(
    encoding
    for encoding in ("utf-8", locale.getpreferredencoding(False), "cp932", "shift_jis")
    if encoding
))


def decode_subprocess_output(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    for encoding in SUBPROCESS_OUTPUT_ENCODINGS:
        try:
            return value.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return value.decode("utf-8", errors="replace")


def iter_subprocess_output_lines(process):
    if not process.stdout:
        return
    for raw_line in process.stdout:
        yield decode_subprocess_output(raw_line).strip()


ASR_MODEL = os.environ.get("GEMMA_ASR_MODEL", "").strip()
ASR_RUNNER = os.environ.get("GEMMA_ASR_RUNNER", "").strip()
ASR_WORKER = os.environ.get("GEMMA_ASR_WORKER", "").strip()
ASR_LANGUAGE = os.environ.get("GEMMA_ASR_LANGUAGE", "ja-JP").strip()
ASR_TIMEOUT = int(os.environ.get("GEMMA_ASR_TIMEOUT", "180"))
DEFAULT_ASR_MODEL = "nvidia/nemotron-3.5-asr-streaming-0.6b"
WHISPER_CPP_MODEL = "whisper.cpp"
WHISPER_CPP_FAST_MODEL = "whisper.cpp:tiny"
WHISPER_CPP_ACCURATE_MODEL = "whisper.cpp:large-v3-turbo"
WHISPER_CPP_BINARY = os.environ.get("GEMMA_WHISPER_CPP_BINARY", "").strip()
WHISPER_CPP_MODEL_PATH = os.environ.get("GEMMA_WHISPER_CPP_MODEL", "").strip()
WHISPER_CPP_FAST_MODEL_PATH = os.environ.get("GEMMA_WHISPER_CPP_FAST_MODEL", "").strip()
WHISPER_CPP_ACCURATE_MODEL_PATH = os.environ.get("GEMMA_WHISPER_CPP_ACCURATE_MODEL", "").strip()
ASR_MODEL_CANDIDATES = [
    {
        "model": "nvidia/nemotron-3.5-asr-streaming-0.6b",
        "label": "NVIDIA Nemotron 3.5 ASR Streaming 0.6B",
        "purpose": "高品質・多言語・ストリーミング",
        "note": "600Mモデル。精度重視向け。NeMo/PyTorch導入が必要で学生PCでは重い可能性があります。",
        "weight": "heavy",
        "source": "https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b",
        "implemented": True,
    },
    {
        "model": "whisper.cpp:tiny",
        "label": "Whisper 高速",
        "purpose": "短い音声を速く文字起こし",
        "note": "tinyモデル。速いですが、聞き間違いが出ることがあります。",
        "weight": "light",
        "source": "https://github.com/ggml-org/whisper.cpp",
        "implemented": False,
    },
    {
        "model": "whisper.cpp:large-v3-turbo",
        "label": "Whisper 高精度",
        "purpose": "正確さ重視の文字起こし",
        "note": "large-v3-turboモデル。高速より遅いですが、日本語の精度が上がります。",
        "weight": "medium",
        "source": "https://github.com/ggml-org/whisper.cpp",
        "implemented": False,
    },
    {
        "model": "vosk",
        "label": "Vosk",
        "purpose": "軽量・オフライン・導入しやすい候補",
        "note": "小型モデルは約50MBから。日本語を含む多言語に対応し、pip導入もしやすい候補です。",
        "weight": "light",
        "source": "https://alphacephei.com/vosk/",
        "implemented": False,
    },
    {
        "model": "sherpa-onnx",
        "label": "sherpa-onnx",
        "purpose": "拡張性重視のオフラインASR候補",
        "note": "ONNX Runtimeベース。Mac/Windows/組み込み環境やWebSocketサーバーまで拡張しやすい候補です。",
        "weight": "medium",
        "source": "https://github.com/k2-fsa/sherpa-onnx",
        "implemented": False,
    },
]
DEFAULT_SYSTEM_PROMPT = (
    "あなたは簡潔で有用なアシスタントです。前置きなしで自然に短く答えてください。"
    "箇条書きは、比較・手順・整理が必要な場合だけ使ってください。"
)
PULLABLE_MODELS = [
    {"model": GEMMA_BASE_MODEL, "label": "Gemma 4 12B", "purpose": "標準チャット・画像理解", "family": "Gemma系"},
    {
        "model": GEMMA_MLX_MODEL,
        "label": "Gemma 4 12B MLX 高速版",
        "purpose": "Apple Silicon向け高速チャット・コード生成",
        "family": "Gemma系",
        "runtime": "MLX",
        "requiresOllama": "0.31.0",
        "note": "Ollama 0.31以降でMTP高速化が有効になります。Apple Silicon向けの推奨高速版です。",
    },
    {
        "model": "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M",
        "label": "Gemma 4 Agentic Coder 12B Q4",
        "purpose": "コード生成・修正・デバッグ",
        "family": "Gemma系",
    },
    {
        "model": "hf.co/HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M",
        "label": "HauhauCS Balanced 12B Q4",
        "purpose": "強化型チャット・制限弱め・PC負荷強",
        "family": "Gemma系",
    },
    {"model": "qwen2.5:3b", "label": "Qwen 2.5 3B", "purpose": "高速チャット・翻訳", "family": "Qwen系"},
    {
        "model": "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL",
        "label": "Qwen3 4B Instruct 2507",
        "purpose": "軽量標準・資料検索・学習パック",
        "family": "Qwen系",
        "role": "lightweight-standard",
        "defaultContext": 8192,
        "maxContext": 32768,
        "advancedContext": 262144,
        "note": "Qwen公式モデルのUnsloth GGUF量子化版です。既存の qwen3:4b とは別候補です。",
    },
    {
        "model": "hf.co/mradermacher/Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated-GGUF:Q4_K_M",
        "label": "Huihui Gemma 4 Coder 12B Abliterated",
        "purpose": "コード実験・制限弱め・上級者向け",
        "family": "実験モデル",
        "role": "coding-experimental",
        "experimental": True,
        "defaultVisible": False,
        "allowAutoSelect": False,
        "safetyLevel": "low",
        "blockedFor": [
            "student-default",
            "company-documents",
            "external-send-check",
            "study-pack-default",
            "adult-mode-default",
        ],
        "warning": "通常の安全調整が弱い可能性があります。学生向け標準、社内文書、外部送信前チェックには推奨しません。",
    },
]
PULLABLE_MODEL_NAMES = {item["model"] for item in PULLABLE_MODELS if item["model"] and item.get("pullable") is not False}
MODEL_PULL_JOBS: dict[str, dict[str, object]] = {}
MODEL_PULL_LOCK = threading.Lock()
ASR_SETUP_JOB: dict[str, object] = {}
ASR_SETUP_LOCK = threading.Lock()
OCR_SETUP_JOB: dict[str, object] = {}
OCR_SETUP_LOCK = threading.Lock()
INTERNET_LAYER_SETUP_JOB: dict[str, object] = {}
INTERNET_LAYER_SETUP_LOCK = threading.Lock()
ASR_WORKER_PROCESS: subprocess.Popen | None = None
ASR_WORKER_OUTPUTS: queue.Queue[str] = queue.Queue()
ASR_WORKER_LOCK = threading.Lock()
IMAGE_PROMPT_SYSTEM = (
    "Convert the user's image request into one concise English Stable Diffusion prompt. "
    "Preserve the exact subject. If the subject is simple, make it explicit and recognizable. "
    "Return only the prompt, with no quotes, no labels, and no explanation."
)
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_WEATHER_LOCATION = os.environ.get("GEMMA_WEATHER_LOCATION", "東京")
MAX_TREE_FILES = 700
MAX_FILE_BYTES = 120_000
MAX_CONTEXT_CHARS = 80_000
MAX_SEARCH_FILES = 2_000
MAX_SEARCH_FILE_BYTES = 300_000
MAX_DOCUMENT_CONTEXT_BYTES = 8_000_000
MAX_ATTACHMENT_BYTES = 12_000_000
MAX_SEARCH_RESULTS = 80
MAX_IMAGES_PER_MESSAGE = 4
MAX_IMAGE_BASE64_CHARS = 12_000_000
COMFYUI_DEFAULT_PREFIX = "Gemma4UI"
_OLLAMA_MODELS_CACHE: dict[str, object] = {"at": 0.0, "models": set()}
_GIT_COMMIT_CACHE: str | None = None
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
    ".codegraph",
}
CODEGRAPH_DIR_NAME = ".codegraph"
CODEGRAPH_SUMMARY_FILE = "summary.json"
CODEGRAPH_APP_CACHE_DIR = ROOT / ".gemma4-data" / "codegraph"
CODEGRAPH_MAX_FILES = 350
CODEGRAPH_MAX_FILE_BYTES = 220_000
CODEGRAPH_MAX_SYMBOLS_PER_FILE = 24
CODEGRAPH_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
}


def codegraph_cache_path(root_path: Path) -> Path:
    cache_id = uuid.uuid5(uuid.NAMESPACE_URL, str(root_path)).hex
    return CODEGRAPH_APP_CACHE_DIR / f"{cache_id}.json"
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
SEARCHABLE_DOCUMENT_EXTENSIONS = {".docx", ".pdf"}
CONTRACT_IMPORT_GAP_EXTENSIONS = {".pdf", ".docx"}
OCR_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
WEATHER_CODES = {
    0: "快晴",
    1: "晴れ",
    2: "一部曇り",
    3: "曇り",
    45: "霧",
    48: "霧氷を伴う霧",
    51: "弱い霧雨",
    53: "霧雨",
    55: "強い霧雨",
    56: "弱い着氷性霧雨",
    57: "強い着氷性霧雨",
    61: "弱い雨",
    63: "雨",
    65: "強い雨",
    66: "弱い着氷性の雨",
    67: "強い着氷性の雨",
    71: "弱い雪",
    73: "雪",
    75: "強い雪",
    77: "霧雪",
    80: "弱いにわか雨",
    81: "にわか雨",
    82: "強いにわか雨",
    85: "弱いにわか雪",
    86: "強いにわか雪",
    95: "雷雨",
    96: "ひょうを伴う雷雨",
    99: "強いひょうを伴う雷雨",
}
WEATHER_LOCATION_ALIASES = {
    "東京": "Tokyo",
    "東京都": "Tokyo",
    "大阪": "Osaka",
    "大阪府": "Osaka",
    "京都": "Kyoto",
    "京都府": "Kyoto",
    "名古屋": "Nagoya",
    "新潟": "Niigata",
    "新潟市": "Niigata",
    "新潟県": "Niigata",
    "横浜": "Yokohama",
    "神奈川": "Yokohama",
    "札幌": "Sapporo",
    "北海道": "Sapporo",
    "仙台": "Sendai",
    "福岡": "Fukuoka",
    "広島": "Hiroshima",
    "神戸": "Kobe",
    "沖縄": "Naha",
    "那覇": "Naha",
}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def svg_response(handler: BaseHTTPRequestHandler, status: int, body: str) -> None:
    payload = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "image/svg+xml; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(payload)


def stream_json_event(handler: BaseHTTPRequestHandler, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
    handler.wfile.write(body)
    handler.wfile.flush()


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def person_photo_upload_payload(name: str, mime: str, base64_value: str) -> dict:
    normalized_mime = (mime or "").split(";")[0].strip().lower()
    suffix = PERSON_PHOTO_MIME_EXTENSIONS.get(normalized_mime)
    if not suffix:
        return {"ok": False, "error": "unsupported image type"}
    raw_value = (base64_value or "").strip()
    if raw_value.startswith("data:"):
        if "," not in raw_value:
            return {"ok": False, "error": "invalid image data"}
        raw_value = raw_value.split(",", 1)[1]
    try:
        body = base64.b64decode(raw_value, validate=True)
    except (binascii.Error, ValueError):
        return {"ok": False, "error": "invalid image data"}
    if not body:
        return {"ok": False, "error": "empty image data"}
    if len(body) > PERSON_PHOTO_MAX_BYTES:
        return {"ok": False, "error": "image too large"}
    PERSON_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    (PERSON_PHOTO_DIR / stored_name).write_bytes(body)
    return {
        "ok": True,
        "file": stored_name,
        "name": Path(name or stored_name).name,
        "mime": normalized_mime,
        "size": len(body),
        "url": f"/api/person-photo/view?file={urllib.parse.quote(stored_name)}",
    }


def is_lan_ipv4_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.version == 4 and ip.is_private and not ip.is_loopback and not ip.is_link_local


def lan_ipv4_sort_key(address: str) -> tuple[int, str]:
    if address.startswith("192.168."):
        return (0, address)
    if address.startswith("172.20."):
        return (1, address)
    if address.startswith("10."):
        return (2, address)
    return (3, address)


def local_lan_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        hostname = socket.gethostname()
        for result in socket.getaddrinfo(hostname, None, socket.AF_INET):
            address = result[4][0]
            if address and is_lan_ipv4_address(address):
                addresses.add(address)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = str(probe.getsockname()[0])
            if is_lan_ipv4_address(address):
                addresses.add(address)
    except OSError:
        pass
    try:
        result = subprocess.run(
            ["ifconfig"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        for address in re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)\b", result.stdout or ""):
            if is_lan_ipv4_address(address):
                addresses.add(address)
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(addresses, key=lan_ipv4_sort_key)


def set_mobile_pairing_code(pairing_code: str, expires_at_epoch: float) -> None:
    MOBILE_PAIRING_STATE.clear()
    MOBILE_PAIRING_STATE.update({
        "pairingCode": pairing_code,
        "expiresAtEpoch": expires_at_epoch,
    })


def mobile_pairing_code_is_valid(pairing_code: str, now: float | None = None) -> bool:
    current_time = time.time() if now is None else now
    expected = str(MOBILE_PAIRING_STATE.get("pairingCode") or "")
    expires_at = float(MOBILE_PAIRING_STATE.get("expiresAtEpoch") or 0)
    return bool(pairing_code and pairing_code == expected and current_time <= expires_at)


def current_or_new_mobile_pairing_code(now: float | None = None) -> tuple[str, float]:
    current_time = time.time() if now is None else now
    existing_code = str(MOBILE_PAIRING_STATE.get("pairingCode") or "")
    existing_expires_at = float(MOBILE_PAIRING_STATE.get("expiresAtEpoch") or 0)
    if existing_code and current_time <= existing_expires_at:
        return existing_code, existing_expires_at
    pairing_code = f"{random.SystemRandom().randint(0, 999999):06d}"
    expires_at_epoch = current_time + MOBILE_PAIRING_TTL_SECONDS
    set_mobile_pairing_code(pairing_code, expires_at_epoch)
    return pairing_code, expires_at_epoch


def mobile_chat_import_summary(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("type") != "gemma4-mobile-chat":
        return {"ok": False, "error": "invalid_payload", "total": 0, "user": 0, "assistant": 0}
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return {"ok": False, "error": "invalid_payload", "total": 0, "user": 0, "assistant": 0}
    valid_messages = [
        message for message in messages
        if isinstance(message, dict)
        and str(message.get("role") or "") in {"user", "assistant"}
        and str(message.get("text") or "").strip()
    ]
    return {
        "ok": True,
        "total": len(valid_messages),
        "user": sum(1 for message in valid_messages if message.get("role") == "user"),
        "assistant": sum(1 for message in valid_messages if message.get("role") == "assistant"),
    }


def mobile_chat_import_fingerprint(payload: dict) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def queue_mobile_chat_import(body: dict, now: float | None = None) -> dict:
    pairing_code = str(body.get("pairingCode") or "")
    if not mobile_pairing_code_is_valid(pairing_code, now=now):
        return {"ok": False, "error": "invalid_pairing_code"}
    payload = body.get("payload")
    summary = mobile_chat_import_summary(payload if isinstance(payload, dict) else {})
    if not summary.get("ok") or int(summary.get("total") or 0) <= 0:
        return {"ok": False, "error": summary.get("error") or "empty_payload", "summary": summary}
    received_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now))
    fingerprint = mobile_chat_import_fingerprint(payload)
    item = {
        "id": uuid.uuid4().hex,
        "receivedAt": received_at,
        "summary": summary,
        "payload": payload,
        "fingerprint": fingerprint,
    }
    with MOBILE_IMPORT_LOCK:
        for existing in MOBILE_PENDING_IMPORTS:
            if existing.get("fingerprint") == fingerprint:
                return {
                    "ok": True,
                    "duplicate": True,
                    "importId": existing.get("id"),
                    "receivedAt": existing.get("receivedAt"),
                    "summary": existing.get("summary") or summary,
                }
        MOBILE_PENDING_IMPORTS.append(item)
    return {"ok": True, "importId": item["id"], "receivedAt": received_at, "summary": summary}


def mobile_pending_imports() -> list[dict[str, object]]:
    with MOBILE_IMPORT_LOCK:
        return [dict(item) for item in MOBILE_PENDING_IMPORTS]


def clear_mobile_pending_imports(ids: list[str] | None = None) -> dict:
    with MOBILE_IMPORT_LOCK:
        if ids is None:
            cleared = len(MOBILE_PENDING_IMPORTS)
            MOBILE_PENDING_IMPORTS.clear()
            return {"ok": True, "cleared": cleared}
        wanted = set(ids)
        before = len(MOBILE_PENDING_IMPORTS)
        MOBILE_PENDING_IMPORTS[:] = [item for item in MOBILE_PENDING_IMPORTS if str(item.get("id")) not in wanted]
        return {"ok": True, "cleared": before - len(MOBILE_PENDING_IMPORTS)}


def mobile_connect_info(
    host: str,
    port: int,
    lan_addresses: list[str] | None = None,
    public_port: int | None = None,
    now: float | None = None,
) -> dict:
    bind_host = str(host or "127.0.0.1")
    normalized_host = bind_host.lower()
    addresses = lan_addresses if lan_addresses is not None else local_lan_ipv4_addresses()
    candidate_port = int(public_port if public_port is not None else port)
    lan_enabled = bool(addresses) or normalized_host not in {"127.0.0.1", "localhost", "::1"}
    host_candidates = [f"http://{address}:{candidate_port}" for address in addresses]
    current_time = time.time() if now is None else now
    pairing_code, expires_at_epoch = current_or_new_mobile_pairing_code(now=current_time)
    expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expires_at_epoch))
    qr_payload = {
        "host": host_candidates[0],
        "pairingCode": pairing_code,
        "expiresAt": expires_at,
    } if host_candidates else {}
    return {
        "ok": True,
        "bindHost": bind_host,
        "port": port,
        "lanAccessEnabled": lan_enabled,
        "pairingEnabled": bool(host_candidates),
        "pairingCode": pairing_code,
        "expiresAt": expires_at,
        "hostCandidates": host_candidates,
        "qrPayload": qr_payload,
    }


def configured_mobile_sync_port(default: int = 54877) -> int:
    try:
        return int(os.environ.get("GEMMA_MOBILE_SYNC_PORT", str(default)))
    except ValueError:
        return default


def local_mobile_sync_connect_info(port: int) -> dict | None:
    url = f"http://127.0.0.1:{port}/api/mobile/connect-info"
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and payload.get("ok"):
        return payload
    return None


def mobile_preview_urls(port: int, lan_addresses: list[str] | None = None) -> list[str]:
    addresses = lan_addresses if lan_addresses is not None else local_lan_ipv4_addresses()
    return [f"http://{address}:{port}" for address in sorted(set(addresses))]


def static_preview_get_api_allowed(path: str, allow_mobile_sync: bool = False) -> bool:
    if not path.startswith("/api/"):
        return True
    if path == "/api/health":
        return True
    return allow_mobile_sync and path.startswith("/api/mobile/")


def is_loopback_client(host: str) -> bool:
    normalized = str(host or "").lower()
    return normalized == "localhost" or normalized == "::1" or normalized.startswith("127.")


def is_local_pc_client(host: str) -> bool:
    normalized = str(host or "").lower()
    return is_loopback_client(normalized) or normalized in set(local_lan_ipv4_addresses())


def mobile_api_access_allowed(method: str, path: str, client_host: str) -> bool:
    normalized_method = str(method or "").upper()
    if normalized_method == "POST" and path == "/api/mobile/import-chat":
        return True
    if path in {"/api/mobile/connect-info", "/api/mobile/imports", "/api/mobile/imports/clear", "/api/mobile/qr.svg"}:
        return is_local_pc_client(client_host)
    return False


def mobile_qr_svg(text: str, scale: int = 8, border: int = 4) -> str:
    if segno is None:
        raise RuntimeError("segno is not installed")
    buffer = io.BytesIO()
    qr = segno.make(text, error="m")
    qr.save(buffer, kind="svg", scale=scale, border=border, xmldecl=False)
    return buffer.getvalue().decode("utf-8")


def python_module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def asr_runner_python_command() -> list[str]:
    if ASR_RUNNER:
        try:
            parts = shlex.split(ASR_RUNNER)
        except ValueError:
            parts = []
        if parts:
            executable = parts[0]
            if executable in {"python", "python3"}:
                resolved = shutil.which(executable) or executable
                return [resolved]
            path = Path(executable)
            if not path.is_absolute():
                path = ROOT / path
            return [str(path)]
    return [sys.executable]


def asr_python_environment_status() -> dict[str, object]:
    command = asr_runner_python_command()
    script = (
        "import importlib.util, json, sys;"
        "mods=["
        "'torch',"
        "'Cython',"
        "'packaging',"
        "'nemo.collections.asr',"
        "'nemo.collections.asr.models.rnnt_bpe_models_prompt'"
        "];"
        "print(json.dumps({"
        "'version': sys.version.split()[0],"
        "'executable': sys.executable,"
        "'modules': {m: importlib.util.find_spec(m) is not None for m in mods}"
        "}))"
    )
    try:
        result = subprocess.run(
            [*command, "-c", script],
            cwd=str(ROOT),
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode == 0:
            payload = json.loads(result.stdout.strip() or "{}")
            if isinstance(payload, dict):
                return payload
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return {
        "version": sys.version.split()[0],
        "executable": command[0] if command else sys.executable,
        "modules": {
            "torch": python_module_available("torch"),
            "Cython": python_module_available("Cython"),
            "packaging": python_module_available("packaging"),
            "nemo.collections.asr": python_module_available("nemo.collections.asr"),
            "nemo.collections.asr.models.rnnt_bpe_models_prompt": python_module_available(
                "nemo.collections.asr.models.rnnt_bpe_models_prompt"
            ),
        },
    }


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(max(size, 0))
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def asr_model_cache_status(model: str) -> dict[str, object]:
    model_name = (model or DEFAULT_ASR_MODEL).strip() or DEFAULT_ASR_MODEL
    cache_home = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache" / "huggingface"))
    hub_root = cache_home / "hub"
    model_dir = hub_root / f"models--{model_name.replace('/', '--')}"
    files = []
    if model_dir.exists():
        files = [path for path in model_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".nemo", ".safetensors", ".bin"}]
    size = sum(path.stat().st_size for path in files if path.exists())
    downloaded = bool(files)
    return {
        "model": model_name,
        "downloaded": downloaded,
        "cacheDir": str(model_dir),
        "files": len(files),
        "sizeBytes": size,
        "sizeText": format_bytes(size) if downloaded else "",
        "detail": f"DL済み / {format_bytes(size)} / {model_dir}" if downloaded else f"未取得 / {model_dir}",
    }


def whisper_cpp_binary_path() -> str:
    candidates = [
        WHISPER_CPP_BINARY,
        shutil.which("whisper-cli") or "",
        shutil.which("whisper-cpp") or "",
        shutil.which("whisper") or "",
        "/opt/homebrew/bin/whisper-cli",
        "/usr/local/bin/whisper-cli",
        "/opt/homebrew/opt/whisper-cpp/bin/whisper-cli",
        "/usr/local/opt/whisper-cpp/bin/whisper-cli",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().exists():
            return str(Path(candidate).expanduser())
    return ""


def normalize_whisper_cpp_model(model: str) -> str:
    requested = (model or "").strip()
    if requested in {"", WHISPER_CPP_MODEL, WHISPER_CPP_FAST_MODEL}:
        return WHISPER_CPP_FAST_MODEL
    if requested == WHISPER_CPP_ACCURATE_MODEL:
        return WHISPER_CPP_ACCURATE_MODEL
    return WHISPER_CPP_FAST_MODEL


def whisper_cpp_display_name(model: str) -> str:
    normalized = normalize_whisper_cpp_model(model)
    if normalized == WHISPER_CPP_ACCURATE_MODEL:
        return "Whisper 高精度"
    return "Whisper 高速"


def is_whisper_cpp_model(model: str) -> bool:
    return (model or "").strip() in {WHISPER_CPP_MODEL, WHISPER_CPP_FAST_MODEL, WHISPER_CPP_ACCURATE_MODEL}


def whisper_cpp_model_path(model: str = WHISPER_CPP_FAST_MODEL) -> str:
    normalized = normalize_whisper_cpp_model(model)
    if normalized == WHISPER_CPP_ACCURATE_MODEL:
        candidates = [
            WHISPER_CPP_ACCURATE_MODEL_PATH,
            str(ROOT / "models" / "whisper" / "ggml-large-v3-turbo.bin"),
            str(ROOT / "models" / "whisper" / "ggml-large-v3-turbo-q5_0.bin"),
            str(Path.home() / "Library" / "Application Support" / "Minimo" / "models" / "ggml-large-v3-turbo.bin"),
            str(Path.home() / "Library" / "Application Support" / "com.prakashjoshipax.VoiceInk" / "WhisperModels" / "ggml-large-v3-turbo-q5_0.bin"),
            str(Path.home() / "Library" / "Application Support" / "com.prakashjoshipax.VoiceInk" / "WhisperModels" / "ggml-large-v3.bin"),
        ]
    else:
        candidates = [
            WHISPER_CPP_MODEL_PATH,
            WHISPER_CPP_FAST_MODEL_PATH,
            str(ROOT / "models" / "whisper" / "ggml-tiny.bin"),
            str(ROOT / "models" / "whisper" / "ggml-base.bin"),
            str(Path.home() / "Library" / "Application Support" / "com.prakashjoshipax.VoiceInk" / "WhisperModels" / "ggml-tiny.bin"),
        ]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().exists():
            return str(Path(candidate).expanduser())
    return ""


def whisper_cpp_status(model: str = WHISPER_CPP_FAST_MODEL) -> dict[str, object]:
    normalized = normalize_whisper_cpp_model(model)
    binary = whisper_cpp_binary_path()
    model_path = whisper_cpp_model_path(normalized)
    return {
        "available": bool(binary and model_path),
        "binary": binary,
        "model": normalized,
        "modelPath": model_path,
        "modelSizeText": format_bytes(Path(model_path).stat().st_size) if model_path else "",
    }


def whisper_cpp_available(model: str = WHISPER_CPP_FAST_MODEL) -> bool:
    return bool(whisper_cpp_status(model).get("available"))


def asr_candidates_payload() -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for candidate in ASR_MODEL_CANDIDATES:
        item = dict(candidate)
        if is_whisper_cpp_model(str(item.get("model") or "")):
            ready = whisper_cpp_available(str(item.get("model") or ""))
            item["implemented"] = ready
            item["status"] = "ready" if ready else "needs_install"
        candidates.append(item)
    return candidates


def runnable_asr_models() -> set[str]:
    return {
        str(candidate.get("model"))
        for candidate in asr_candidates_payload()
        if candidate.get("implemented") and candidate.get("model")
    }


def normalize_asr_model(model: str) -> str:
    requested = (model or "").strip()
    if is_whisper_cpp_model(requested):
        normalized_whisper = normalize_whisper_cpp_model(requested)
        return normalized_whisper if normalized_whisper in runnable_asr_models() else (ASR_MODEL or DEFAULT_ASR_MODEL)
    return requested if requested in runnable_asr_models() else (ASR_MODEL or DEFAULT_ASR_MODEL)


def whisper_cpp_dependency_status(model: str = WHISPER_CPP_FAST_MODEL) -> list[dict[str, object]]:
    binary = whisper_cpp_binary_path()
    model_path = whisper_cpp_model_path(model)
    ffmpeg_path = shutil.which("ffmpeg")
    return [
        {
            "id": "ffmpeg",
            "label": "ffmpeg",
            "ok": bool(ffmpeg_path),
            "detail": ffmpeg_path or "",
            "hint": "ブラウザ録音をWAVへ変換するために必要です。",
        },
        {
            "id": "whisper_cpp",
            "label": "whisper.cpp",
            "ok": bool(binary),
            "detail": binary,
            "hint": "whisper.cpp の実行ファイルが必要です。Macでは brew install whisper-cpp で導入できます。",
        },
        {
            "id": "whisper_model",
            "label": "Whisperモデル",
            "ok": bool(model_path),
            "detail": (
                f"{format_bytes(Path(model_path).stat().st_size)} / {model_path}"
                if model_path
                else ""
            ),
            "hint": "ggml-tiny.bin などのWhisperモデルが必要です。",
        },
    ]


def asr_dependency_status(model: str | None = None) -> list[dict[str, object]]:
    if is_whisper_cpp_model(str(model or "")):
        return whisper_cpp_dependency_status(str(model or ""))

    python_env = asr_python_environment_status()
    modules = python_env.get("modules") if isinstance(python_env.get("modules"), dict) else {}
    version_text = str(python_env.get("version") or "")
    python_ok = tuple(int(part) for part in version_text.split(".")[:2] if part.isdigit()) >= (3, 11)
    ffmpeg_path = shutil.which("ffmpeg")
    model_cache = asr_model_cache_status(normalize_asr_model(ASR_MODEL or DEFAULT_ASR_MODEL))
    requirements = [
        {
            "id": "python",
            "label": "Python 3.11+",
            "ok": python_ok,
            "detail": f"{version_text} / {python_env.get('executable', '')}".strip(" /"),
            "hint": "Python 3.11以上で起動してください。",
        },
        {
            "id": "ffmpeg",
            "label": "ffmpeg",
            "ok": bool(ffmpeg_path),
            "detail": ffmpeg_path or "",
            "hint": "ブラウザ録音をWAVへ変換するために必要です。",
        },
        {
            "id": "torch",
            "label": "PyTorch",
            "ok": bool(modules.get("torch")),
            "detail": "",
            "hint": "Nemotron/NeMoを実行するために必要です。",
        },
        {
            "id": "cython",
            "label": "Cython",
            "ok": bool(modules.get("Cython")),
            "detail": "",
            "hint": "NeMoの導入に必要になることがあります。",
        },
        {
            "id": "packaging",
            "label": "packaging",
            "ok": bool(modules.get("packaging")),
            "detail": "",
            "hint": "NeMo/PyTorch周辺の依存解決に必要です。",
        },
        {
            "id": "nemo",
            "label": "NVIDIA NeMo ASR",
            "ok": bool(modules.get("nemo.collections.asr")),
            "detail": "",
            "hint": "nemo_toolkit[asr] を導入するとNemotronを実行できます。",
        },
        {
            "id": "nemotron_compat",
            "label": "Nemotron対応NeMo",
            "ok": bool(modules.get("nemo.collections.asr.models.rnnt_bpe_models_prompt")),
            "detail": "rnnt_bpe_models_prompt",
            "hint": "Nemotron 3.5 ASRにはNeMo main/26.06相当が必要です。通常のnemo_toolkit[asr]だけでは不足する場合があります。",
        },
        {
            "id": "asr_model_cache",
            "label": "音声モデル本体",
            "ok": bool(model_cache.get("downloaded")),
            "detail": str(model_cache.get("detail") or ""),
            "hint": "未取得の場合は初回文字起こし時に大きなモデルを取得します。通信量と時間がかかります。",
        },
    ]
    return requirements


def asr_status_payload() -> dict:
    model = normalize_asr_model(ASR_MODEL or DEFAULT_ASR_MODEL)
    configured = True if is_whisper_cpp_model(model) else bool(ASR_RUNNER or ASR_WORKER)
    requirements = asr_dependency_status(model)
    model_cache_ok = any(item.get("id") == "asr_model_cache" and item.get("ok") for item in requirements)
    dependency_requirements_ok = all(
        item.get("ok") for item in requirements if item.get("id") != "asr_model_cache"
    )
    requirements_ok = all(item.get("ok") for item in requirements)
    nemotron_compat_ok = any(item.get("id") == "nemotron_compat" and item.get("ok") for item in requirements)
    base_requirements_ok = all(
        item.get("ok") for item in requirements if item.get("id") not in {"nemotron_compat", "asr_model_cache"}
    )
    needs_compatible_nemo = configured and base_requirements_ok and not nemotron_compat_ok
    needs_model_download = configured and dependency_requirements_ok and not model_cache_ok
    status = (
        "ready"
        if configured and requirements_ok
        else "needs_compatible_nemo"
        if needs_compatible_nemo
        else "needs_model_download"
        if needs_model_download
        else "needs_dependencies"
        if configured
        else "not_configured"
    )
    return {
        "ok": True,
        "available": configured and requirements_ok,
        "status": status,
        "model": model,
        "recommendedModel": model,
        "runnerConfigured": configured,
        "runner": ASR_RUNNER,
        "workerConfigured": bool(ASR_WORKER),
        "worker": ASR_WORKER,
        "language": ASR_LANGUAGE,
        "modelCache": whisper_cpp_status(model) if is_whisper_cpp_model(model) else asr_model_cache_status(model),
        "runnableModels": sorted(runnable_asr_models()),
        "requirements": requirements,
        "requirementsOk": requirements_ok,
        "dependenciesOk": dependency_requirements_ok,
        "setupDoc": "docs/asr-nemotron-setup.ja.md",
        "candidates": asr_candidates_payload(),
        "message": (
            f"{whisper_cpp_display_name(model)} は使用できます。モデル: {whisper_cpp_status(model).get('modelSizeText') or '検出済み'}"
            if is_whisper_cpp_model(model) and requirements_ok
            else "whisper.cpp を使うには実行ファイルとWhisperモデルが必要です。"
            if is_whisper_cpp_model(model)
            else
            f"音声入力ランナーは設定済みです。{model} で文字起こしを試します。"
            if configured and requirements_ok and not ASR_WORKER
            else f"音声入力の常駐ワーカーは設定済みです。{model} は初回後の文字起こしが速くなります。"
            if configured and requirements_ok
            else "Nemotron 3.5 ASRに必要なNeMoクラスが見つかりません。NeMo main/26.06相当の導入が必要です。"
            if needs_compatible_nemo
            else f"{model} のモデル本体がまだ見つかりません。初回の文字起こし時にダウンロードが必要です。"
            if needs_model_download
            else "Nemotronランナーは設定済みですが、必要な依存がまだ不足しています。"
            if configured
            else "音声入力はまだ準備中です。Nemotronランナーを設定すると文字起こしを試せます。"
        ),
        "nextStep": (
            "音声認識モデルをWhisperに切り替えて、短い録音で速度を確認します。"
            if is_whisper_cpp_model(model) and requirements_ok
            else "whisper.cpp の導入後、音声認識モデルで whisper.cpp を選びます。"
            if is_whisper_cpp_model(model)
            else
            "音声ボタンで録音し、文字起こし結果が入力欄に入るか確認します。"
            if configured and requirements_ok
            else "設定画面のASRセットアップを更新し、NeMo main/26.06相当で再導入します。重い場合は whisper.cpp など軽量候補を使います。"
            if needs_compatible_nemo
            else "モデル本体を取得してから、マイクボタンで録音を試します。"
            if needs_model_download
            else "設定画面の不足項目を確認し、NeMo/PyTorch/ffmpeg を導入します。"
            if configured
            else "GEMMA_ASR_RUNNER に scripts/asr_nemotron_runner.py を指定し、NeMo/PyTorch/ffmpeg を導入します。"
        ),
    }


def asr_suffix_for_mime(mime_type: str) -> str:
    clean = (mime_type or "").split(";")[0].strip().lower()
    if clean in {"audio/wav", "audio/wave", "audio/x-wav"}:
        return ".wav"
    if clean in {"audio/mp4", "audio/m4a", "audio/x-m4a"}:
        return ".m4a"
    if clean == "audio/ogg":
        return ".ogg"
    return ".webm"


def ensure_wav_audio(audio_path: Path, mime_type: str) -> tuple[Path, Path | None]:
    clean = (mime_type or "").split(";")[0].strip().lower()
    if clean in {"audio/wav", "audio/wave", "audio/x-wav"} or audio_path.suffix.lower() == ".wav":
        return audio_path, None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("音声変換に必要なffmpegが見つかりません。")
    temp_dir = Path(tempfile.mkdtemp(prefix="gemma4-asr-wav-"))
    wav_path = temp_dir / "input.wav"
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(result.stderr.strip() or "ffmpegで音声をWAVへ変換できませんでした。")
    return wav_path, temp_dir


def clean_whisper_cpp_output(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        clean = re.sub(r"^\s*\[[^\]]+\]\s*", "", line).strip()
        if not clean:
            continue
        if clean.lower().startswith(("whisper_", "system_info:", "main:", "ggml_")):
            continue
        lines.append(clean)
    return " ".join(" ".join(lines).split()).strip()


def run_whisper_cpp_transcription(audio_path: Path, mime_type: str, model: str = WHISPER_CPP_FAST_MODEL) -> dict:
    normalized_model = normalize_whisper_cpp_model(model)
    status = whisper_cpp_status(normalized_model)
    binary = str(status.get("binary") or "")
    model_path = str(status.get("modelPath") or "")
    if not binary:
        raise RuntimeError("whisper.cpp の実行ファイルが見つかりません。Macでは brew install whisper-cpp で導入できます。")
    if not model_path:
        raise RuntimeError("Whisperモデルが見つかりません。ggml-tiny.bin などのモデルを配置してください。")
    wav_path, temp_dir = ensure_wav_audio(audio_path, mime_type)
    try:
        language = "ja" if ASR_LANGUAGE.lower().startswith("ja") else ASR_LANGUAGE.split("-")[0]
        command = [
            binary,
            "-m",
            model_path,
            "-f",
            str(wav_path),
            "-l",
            language or "auto",
            "-nt",
            "-np",
            "--no-gpu",
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=ASR_TIMEOUT,
            check=False,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        text = clean_whisper_cpp_output(stdout) or clean_whisper_cpp_output(stderr)
        if result.returncode != 0:
            raise RuntimeError(stderr.strip() or stdout.strip() or "whisper.cpp が文字起こしに失敗しました。")
        if not text:
            raise RuntimeError("whisper.cpp の文字起こし結果が空でした。")
        return {
            "ok": True,
            "text": text,
            "model": normalized_model,
            "language": ASR_LANGUAGE,
            "engine": WHISPER_CPP_MODEL,
            "binary": binary,
            "modelPath": model_path,
        }
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


def start_asr_worker_process() -> subprocess.Popen:
    global ASR_WORKER_PROCESS
    if not ASR_WORKER:
        raise RuntimeError("ASR常駐ワーカーが未設定です。")
    if ASR_WORKER_PROCESS and ASR_WORKER_PROCESS.poll() is None:
        return ASR_WORKER_PROCESS

    command = shlex.split(ASR_WORKER)
    if not command:
        raise RuntimeError("ASR常駐ワーカーの起動コマンドが空です。")
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    ASR_WORKER_PROCESS = process

    def read_worker_stdout() -> None:
        if not process.stdout:
            return
        for line in process.stdout:
            line = line.strip()
            if line:
                ASR_WORKER_OUTPUTS.put(line)

    threading.Thread(target=read_worker_stdout, daemon=True).start()
    return process


def run_asr_worker_transcription(audio_path: Path, mime_type: str, model: str) -> dict:
    with ASR_WORKER_LOCK:
        while not ASR_WORKER_OUTPUTS.empty():
            try:
                ASR_WORKER_OUTPUTS.get_nowait()
            except queue.Empty:
                break
        process = start_asr_worker_process()
        if not process.stdin:
            raise RuntimeError("ASR常駐ワーカーへ入力できません。")
        request = {
            "audio": str(audio_path),
            "mimeType": mime_type or "audio/webm",
            "model": model,
            "language": ASR_LANGUAGE,
        }
        process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        process.stdin.flush()

        deadline = time.time() + ASR_TIMEOUT
        last_line = ""
        while time.time() < deadline:
            try:
                line = ASR_WORKER_OUTPUTS.get(timeout=min(1, max(0.1, deadline - time.time())))
            except queue.Empty:
                if process.poll() is not None:
                    raise RuntimeError("ASR常駐ワーカーが終了しました。")
                continue
            last_line = line
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not payload.get("ok"):
                raise RuntimeError(str(payload.get("error") or "ASR常駐ワーカーが文字起こしできませんでした。"))
            return payload
        raise TimeoutError(f"ASR常駐ワーカーが{ASR_TIMEOUT}秒以内に応答しませんでした: {last_line[:160]}")


def run_asr_transcription(audio_base64: str, mime_type: str, model: str) -> dict:
    if not is_whisper_cpp_model(model) and not ASR_RUNNER and not ASR_WORKER:
        raise RuntimeError(
            "Nemotronで音声を受け取りましたが、ASRランナーが未設定です。"
            "GEMMA_ASR_RUNNER に scripts/asr_nemotron_runner.py を指定してください。"
        )
    if not audio_base64.strip():
        raise ValueError("音声データが空です。もう一度録音してください。")
    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("音声データを読み取れませんでした。") from exc

    suffix = asr_suffix_for_mime(mime_type)
    with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as handle:
        handle.write(audio_bytes)
        audio_path = Path(handle.name)
    try:
        if is_whisper_cpp_model(model):
            payload = run_whisper_cpp_transcription(audio_path, mime_type, model)
        elif ASR_WORKER:
            payload = run_asr_worker_transcription(audio_path, mime_type, model)
        else:
            command = shlex.split(ASR_RUNNER) + [
                "--audio",
                str(audio_path),
                "--model",
                model,
                "--mime-type",
                mime_type or "audio/webm",
                "--language",
                ASR_LANGUAGE,
            ]
            result = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=ASR_TIMEOUT,
                check=False,
            )
            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            if result.returncode != 0:
                if stdout:
                    try:
                        error_payload = json.loads(stdout)
                        raise RuntimeError(str(error_payload.get("error") or stdout))
                    except json.JSONDecodeError:
                        pass
                raise RuntimeError(stderr or stdout or "ASRランナーが失敗しました。")
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"ASRランナーの出力を読み取れませんでした: {stdout[:300]}") from exc
            if not payload.get("ok"):
                raise RuntimeError(str(payload.get("error") or "ASRランナーが文字起こしできませんでした。"))
        return {
            "ok": True,
            "text": str(payload.get("text") or "").strip(),
            "model": model,
            "language": payload.get("language") or ASR_LANGUAGE,
            "mimeType": mime_type or "audio/webm",
            "audioBytesApprox": len(audio_bytes),
        }
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass


def normalize_local_llm_base_url(raw_url: str) -> str:
    value = str(raw_url or "").strip().rstrip("/")
    if not value:
        return OLLAMA_URL
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URLは http://127.0.0.1:ポート または http://localhost:ポート の形式にしてください。")
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("安全のため、外部LLMサーバーはこのPC上の localhost / 127.0.0.1 のみ指定できます。")
    return f"{parsed.scheme}://{parsed.netloc}"


def ollama_json(path: str, payload: dict | None = None, timeout: int = 120, base_url: str | None = None) -> dict:
    url = f"{base_url or OLLAMA_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_stream(path: str, payload: dict, timeout: int = 600, base_url: str | None = None):
    url = f"{base_url or OLLAMA_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Accept": "application/x-ndjson", "Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(request, timeout=timeout)


def installed_ollama_models(force_refresh: bool = False) -> set[str]:
    now = time.time()
    if not force_refresh and now - float(_OLLAMA_MODELS_CACHE["at"]) < 60:
        return set(_OLLAMA_MODELS_CACHE["models"])
    tags = ollama_json("/api/tags", timeout=3).get("models", [])
    models = {str(item.get("name", "")) for item in tags if item.get("name")}
    _OLLAMA_MODELS_CACHE["at"] = now
    _OLLAMA_MODELS_CACHE["models"] = models
    return models


def select_translation_model() -> str:
    models = installed_ollama_models()
    if TRANSLATION_MODEL and TRANSLATION_MODEL in models:
        return TRANSLATION_MODEL
    for candidate in TRANSLATION_MODEL_CANDIDATES:
        if candidate in models:
            return candidate
    return MODEL


def select_coding_model() -> str:
    return CODING_MODEL or MODEL


def app_commit() -> str:
    global _GIT_COMMIT_CACHE
    if _GIT_COMMIT_CACHE is not None:
        return _GIT_COMMIT_CACHE
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
        _GIT_COMMIT_CACHE = result.stdout.strip()
    except Exception:
        _GIT_COMMIT_CACHE = ""
    return _GIT_COMMIT_CACHE


def friendly_ollama_error(error_body: str) -> str:
    try:
        data = json.loads(error_body)
        message = str(data.get("error") or error_body)
    except Exception:
        message = error_body
    match = re.search(r"model ['\"]?([^'\"\s]+)['\"]? not found", message, flags=re.IGNORECASE)
    if match:
        model = match.group(1)
        return (
            f"モデルが未取得です: {model}\n"
            "使うには設定画面の「モデルをダウンロード」から取得してください。\n"
            f"ターミナルで行う場合: ollama pull {model}"
        )
    return message


def ollama_http_error_event(exc: urllib.error.HTTPError, model: str = "") -> dict:
    error_body = exc.read().decode("utf-8", errors="replace")
    event = {
        "ok": False,
        "type": "error",
        "status": exc.code,
        "error": friendly_ollama_error(error_body),
    }
    if model:
        event["model"] = model
    return event


def translation_target_from_text(text: str) -> str:
    if re.search(r"英訳|英語に|英語へ|to\s+english|into\s+english", text, flags=re.IGNORECASE):
        return "English"
    if re.search(r"和訳|日本語に|日本語へ|to\s+japanese|into\s+japanese", text, flags=re.IGNORECASE):
        return "Japanese"
    source = strip_translation_instruction(text)
    japanese_chars = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]", source))
    latin_chars = len(re.findall(r"[A-Za-z]", source))
    if latin_chars > 0 and japanese_chars == 0:
        return "Japanese"
    if japanese_chars > 0 and latin_chars == 0:
        return "English"
    if latin_chars > japanese_chars * 2:
        return "Japanese"
    if japanese_chars > 0:
        return "English"
    return "Japanese"


def strip_translation_instruction(text: str) -> str:
    cleaned = text.strip()
    lines = cleaned.splitlines()
    instruction_re = re.compile(
        r"^\s*(?:"
        r"日本語\s*に\s*(?:やく|訳|翻訳)?\s*して(?:ください|下さい)?|"
        r"英語\s*に\s*(?:やく|訳|翻訳)?\s*して(?:ください|下さい)?|"
        r"英訳|和訳|翻訳|訳|"
        r"(?:please\s+)?translate(?:\s+(?:this|it|the\s+following|to\s+\w+|into\s+\w+))*"
        r")\s*[。.!！?？]*\s*(?:[:：\-]\s*)?$",
        flags=re.IGNORECASE,
    )
    while lines and (not lines[0].strip() or instruction_re.match(lines[0])):
        lines.pop(0)
    if lines:
        cleaned = "\n".join(lines).strip()
    cleaned = re.sub(
        r"^\s*(?:日本語\s*に\s*(?:やく|訳|翻訳)?\s*して|英語\s*に\s*(?:やく|訳|翻訳)?\s*して|英訳|和訳|翻訳|訳)(?:して|してください|して下さい|お願いします|してほしい)?"
        r"\s*[。.!！?？]*\s*(?:[:：\-]\s*)?",
        "",
        cleaned,
    ).strip()
    cleaned = re.sub(
        r"^\s*(?:please\s+)?translate(?:\s+(?:this|it|the\s+following|to\s+\w+|into\s+\w+))*"
        r"\s*[.!?]*\s*(?:[:：\-]\s*)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned or text.strip()


def clean_translation_output(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(
        r"^(?:english\s+translations?|japanese\s+translations?|translation|translated\s+text|訳|英訳|和訳|翻訳)\s*[:：]\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    lines = cleaned.splitlines()
    while lines and re.match(
        r"^\s*(?:english\s+translations?|japanese\s+translations?|translation|translated\s+text|訳|英訳|和訳|翻訳)\s*[:：]\s*$",
        lines[0],
        flags=re.IGNORECASE,
    ):
        lines.pop(0)
    while len(lines) > 1 and re.match(r"^\s*(?:japanese\s+greetings?|english\s+translations?)\s*[:：]\s*$", lines[-1], flags=re.IGNORECASE):
        lines.pop()
    cleaned = "\n".join(lines).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


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


def weather_description(code: object) -> str:
    try:
        return WEATHER_CODES.get(int(code), f"不明な天気コード {code}")
    except Exception:
        return "不明"


def weather_day_offset_from_text(text: str) -> int:
    if re.search(r"今週|週間|一週間|1週間|週の|weekly|this\s+week", text, flags=re.IGNORECASE):
        return 6
    return 1 if re.search(r"明日|tomorrow", text, flags=re.IGNORECASE) else 0


def weather_location_from_query(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"[?？。!！]", "", cleaned)
    cleaned = re.sub(r"(教えて|おしえて|ください|下さい|どう|ですか|は)$", "", cleaned)
    cleaned = re.sub(r"(今週|週間|一週間|1週間|週の|weekly|this\s+week)(?:の)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(今日|本日|現在|今|いま|明日|tomorrow|today)(?:の)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(天気|気温|降水|雨|晴れ|曇り|weather|temperature|forecast).*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(の|で|における|at|in|for)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(の|で|における|at|in|for)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    return cleaned if cleaned else ""


def weather_request_parts(query: str, location: str) -> tuple[str, int]:
    source = query or location
    day_offset = weather_day_offset_from_text(source)
    parsed_location = weather_location_from_query(source) if query else ""
    selected_location = parsed_location or location.strip() or DEFAULT_WEATHER_LOCATION
    return selected_location, day_offset


def geocode_location(location: str) -> dict:
    requested_name = location.strip() or DEFAULT_WEATHER_LOCATION
    name = WEATHER_LOCATION_ALIASES.get(requested_name, requested_name)
    query = urllib.parse.urlencode({"name": name, "count": 1, "language": "ja", "format": "json"})
    request = urllib.request.Request(
        f"{GEOCODING_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 Gemma4LocalWebUI/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
    results = data.get("results") or []
    if not results:
        raise ValueError(f"場所が見つかりませんでした: {name}")
    result = results[0]
    return {
        "name": result.get("name") or name,
        "admin1": result.get("admin1") or "",
        "country": result.get("country") or "",
        "latitude": result.get("latitude"),
        "longitude": result.get("longitude"),
        "timezone": result.get("timezone") or "auto",
    }


def weather_place_from_coordinates(coordinates: object) -> dict | None:
    if not isinstance(coordinates, dict):
        return None
    try:
        latitude = float(coordinates.get("latitude"))
        longitude = float(coordinates.get("longitude"))
        accuracy_value = coordinates.get("accuracy")
        accuracy = float(accuracy_value) if accuracy_value is not None else None
    except Exception:
        return None
    if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
        return None
    return {
        "name": "現在地",
        "admin1": "",
        "country": "",
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "locationSource": "browser",
        "accuracy": accuracy if accuracy and accuracy > 0 else None,
    }


def fetch_weather(location: str, day_offset: int = 0, coordinates: object = None) -> dict:
    day_offset = max(0, min(day_offset, 6))
    forecast_days = 7 if day_offset >= 2 else day_offset + 1
    place = weather_place_from_coordinates(coordinates) or geocode_location(location)
    query = urllib.parse.urlencode(
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                ]
            ),
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": place["timezone"],
            "forecast_days": forecast_days,
        }
    )
    request = urllib.request.Request(
        f"{FORECAST_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 Gemma4LocalWebUI/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        forecast = json.loads(response.read().decode("utf-8"))
    current = forecast.get("current") or {}
    current_units = forecast.get("current_units") or {}
    daily = forecast.get("daily") or {}
    location_label = " / ".join([item for item in [place["name"], place["admin1"], place["country"]] if item])
    daily_weather = daily.get("weather_code") or []
    daily_max = daily.get("temperature_2m_max") or []
    daily_min = daily.get("temperature_2m_min") or []
    daily_precipitation = daily.get("precipitation_probability_max") or []
    daily_time = daily.get("time") or []
    daily_forecasts = []
    for index, date in enumerate(daily_time[:forecast_days]):
        daily_forecasts.append(
            {
                "date": date,
                "weather": weather_description(daily_weather[index] if len(daily_weather) > index else None),
                "temperatureMax": daily_max[index] if len(daily_max) > index else None,
                "temperatureMin": daily_min[index] if len(daily_min) > index else None,
                "precipitationProbability": daily_precipitation[index] if len(daily_precipitation) > index else None,
            }
        )
    target_index = min(day_offset, max(len(daily_time) - 1, 0))
    return {
        "location": location_label,
        "timezone": forecast.get("timezone") or place["timezone"],
        "dayOffset": day_offset,
        "period": "week" if day_offset >= 2 else "day",
        "locationSource": place.get("locationSource") or "geocoding",
        "coordinates": {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "accuracy": place.get("accuracy"),
        },
        "current": {
            "time": current.get("time"),
            "weather": weather_description(current.get("weather_code")),
            "temperature": current.get("temperature_2m"),
            "temperatureUnit": current_units.get("temperature_2m", "°C"),
            "apparentTemperature": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "windSpeed": current.get("wind_speed_10m"),
        },
        "target": {
            "date": daily_time[target_index] if len(daily_time) > target_index else None,
            "label": "明日" if day_offset == 1 else "今日",
            "weather": weather_description(daily_weather[target_index] if len(daily_weather) > target_index else None),
            "temperatureMax": daily_max[target_index] if len(daily_max) > target_index else None,
            "temperatureMin": daily_min[target_index] if len(daily_min) > target_index else None,
            "precipitationProbability": daily_precipitation[target_index] if len(daily_precipitation) > target_index else None,
        },
        "dailyForecasts": daily_forecasts,
        "source": "Open-Meteo",
    }


def build_weather_answer(weather: dict) -> str:
    current = weather["current"]
    target = weather["target"]
    unit = current.get("temperatureUnit") or "°C"
    source_note = ""
    if weather.get("locationSource") == "browser":
        coordinates = weather.get("coordinates") or {}
        latitude = coordinates.get("latitude")
        longitude = coordinates.get("longitude")
        accuracy = coordinates.get("accuracy")
        coordinate_note = ""
        if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
            coordinate_note = f"（緯度 {latitude:.4f} / 経度 {longitude:.4f}"
            if isinstance(accuracy, (int, float)):
                coordinate_note += f" / 精度 約{round(accuracy)}m"
            coordinate_note += "）"
        source_note = f"位置情報: ブラウザの現在地{coordinate_note}"
    if weather.get("period") == "week":
        lines = [
            f"{weather['location']}の今週の予報です。",
            *[
                f"- {item['date']}: {item['weather']}、最高{item['temperatureMax']}{unit} / 最低{item['temperatureMin']}{unit}、降水確率は最大{item['precipitationProbability']}%"
                for item in weather.get("dailyForecasts", [])
            ],
            f"現在は{current['weather']}、気温{current['temperature']}{unit}、湿度{current['humidity']}%です。",
            f"更新時刻: {current['time']}（{weather['timezone']}） / 出典: {weather['source']}",
        ]
    elif weather.get("dayOffset") == 1:
        lines = [
            f"{weather['location']}の明日（{target['date']}）の予報は{target['weather']}です。",
            f"最高{target['temperatureMax']}{unit} / 最低{target['temperatureMin']}{unit}、降水確率は最大{target['precipitationProbability']}%です。",
            f"参考として現在は{current['weather']}、気温{current['temperature']}{unit}、湿度{current['humidity']}%です。",
            f"更新時刻: {current['time']}（{weather['timezone']}） / 出典: {weather['source']}",
        ]
    else:
        lines = [
            f"{weather['location']}の現在の天気は{current['weather']}です。",
            f"気温は{current['temperature']}{unit}、体感は{current['apparentTemperature']}{unit}、湿度は{current['humidity']}%です。",
            f"今日の予報は{target['weather']}、最高{target['temperatureMax']}{unit} / 最低{target['temperatureMin']}{unit}、降水確率は最大{target['precipitationProbability']}%です。",
            f"風速は{current['windSpeed']} km/h、降水量は{current['precipitation']} mmです。",
            f"更新時刻: {current['time']}（{weather['timezone']}） / 出典: {weather['source']}",
        ]
    if source_note:
        lines.append(source_note)
    return "\n".join(lines)


def resolve_workspace_root(root: str) -> Path:
    path = Path(root).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError("フォルダーが見つかりません。フォルダー編集で参照先を選び直してください。")
    return path


def pick_workspace_folder() -> dict:
    if sys.platform == "darwin":
        script = 'POSIX path of (choose folder with prompt "フォルダーを選択")'
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
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


def contract_pdf_payload_from_path(path_value: str) -> dict[str, object]:
    path = Path(str(path_value or "")).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError("PDFファイルが見つかりません。")
    if path.suffix.lower() != ".pdf":
        raise ValueError("PDFファイルを選択してください。")
    return {"ok": True, "path": str(path)}


def pick_contract_pdf_import_file() -> dict[str, object]:
    if sys.platform == "darwin":
        script = 'POSIX path of (choose file with prompt "PDFファイルを選択")'
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if result.returncode != 0:
            raise ValueError((result.stderr or "PDF選択がキャンセルされました。").strip())
        selected = result.stdout.strip()
    else:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(title="PDFファイルを選択", filetypes=[("PDF", "*.pdf")])
        root.destroy()
        if not selected:
            raise ValueError("PDF選択がキャンセルされました。")
    return contract_pdf_payload_from_path(selected)


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
    search_capabilities = workspace_search_capabilities()
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
            suffix = path.suffix.lower()
            is_document = suffix in SEARCHABLE_DOCUMENT_EXTENSIONS
            is_ocr_image = suffix in OCR_IMAGE_EXTENSIONS
            is_text_file = info.st_size <= MAX_FILE_BYTES and is_probably_text(path)
            can_read_document = is_document and info.st_size <= MAX_DOCUMENT_CONTEXT_BYTES and (
                suffix == ".docx" or bool(search_capabilities.get("pdf"))
            )
            can_read_ocr_image = is_ocr_image and info.st_size <= MAX_DOCUMENT_CONTEXT_BYTES and bool(
                search_capabilities.get("imageOcr")
            )
            files.append(
                {
                    "path": rel,
                    "size": info.st_size,
                    "text": is_text_file or can_read_document or can_read_ocr_image,
                    "kind": (
                        suffix.lstrip(".")
                        if is_document
                        else ("image" if is_ocr_image else ("text" if is_text_file else "binary"))
                    ),
                }
            )
            if len(files) >= MAX_TREE_FILES:
                skipped += 1
                return {"root": str(root_path), "files": files, "truncated": True, "skipped": skipped}
    return {"root": str(root_path), "files": files, "truncated": False, "skipped": skipped}


DOCUMENT_SEARCH_TERMS = {
    "契約書": ["契約書", "契約", "合意書", "覚書", "NDA", "秘密保持", "agreement", "contract"],
    "contract": ["contract", "agreement", "nda", "契約書", "契約", "秘密保持"],
    "agreement": ["agreement", "contract", "nda", "契約書", "契約", "合意書", "覚書"],
    "請求書": ["請求書", "請求", "invoice", "billing", "支払", "振込"],
    "invoice": ["invoice", "billing", "請求書", "請求", "支払"],
    "仕様書": ["仕様書", "仕様", "要件", "設計書", "specification", "spec", "requirements"],
    "spec": ["spec", "specification", "requirements", "仕様書", "仕様", "要件"],
    "specification": ["specification", "spec", "requirements", "仕様書", "仕様", "要件"],
    "見積書": ["見積書", "見積", "estimate", "quotation", "quote"],
    "estimate": ["estimate", "quotation", "quote", "見積書", "見積"],
    "quotation": ["quotation", "estimate", "quote", "見積書", "見積"],
    "領収書": ["領収書", "領収", "receipt", "支払", "入金"],
    "receipt": ["receipt", "領収書", "領収", "支払", "入金"],
    "議事録": ["議事録", "会議メモ", "会議", "minutes", "meeting notes"],
    "minutes": ["minutes", "meeting notes", "議事録", "会議メモ", "会議"],
}


def search_query_terms(query: str) -> list[str]:
    base = str(query or "").strip()
    if not base:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for term in [base, *DOCUMENT_SEARCH_TERMS.get(base.lower(), []), *DOCUMENT_SEARCH_TERMS.get(base, [])]:
        normalized = str(term or "").strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            terms.append(normalized)
    return terms[:14]


def workspace_text_contains_search_term(text: str, term: str) -> bool:
    needle = str(term or "").strip().lower()
    if not needle:
        return False
    haystack = str(text or "").lower()
    if re.fullmatch(r"[a-z0-9]+", needle):
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    return needle in haystack


def extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""
    paragraphs: list[str] = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        parts = [
            text.text or ""
            for text in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
        ]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def contract_pdf_import_status_payload() -> dict[str, object]:
    sarashina = sarashina_ocr_status()
    pdf_import = {
        "id": "contract-pdf-import",
        "label": "契約書PDF取り込み",
        "status": "not-connected",
        "runnerConnected": False,
        "defaultEnabled": True,
        "models": [
            {
                "id": "glm-ocr",
                "label": "GLM-OCR",
                "purpose": "画像PDF向けの推奨OCR",
                "status": "recommended",
            },
            {
                "id": "sarashina2.2-ocr",
                "label": "Sarashina OCR",
                "purpose": "日本語文書OCRの比較用",
                "status": sarashina.get("status") or "candidate",
                "available": bool(sarashina.get("available")),
            },
        ],
        "note": (
            "Sarashina OCRをローカル比較できます。外部API呼び出しは行いません。CPU実行では1ページ数分かかる場合があります。"
            if sarashina.get("available")
            else "PDFテキスト抽出を先に試し、画像PDFなど必要な場合だけOCRを使います。外部API呼び出しは行いません。"
        ),
        "sarashina": sarashina,
    }
    return {
        "ok": True,
        "pdfImport": pdf_import,
    }


def contract_pdf_import_connection_test_payload() -> dict[str, object]:
    ocr = ocr_capabilities()
    return {
        "ok": True,
        "pdfImportId": "contract-pdf-import",
        "runnerConnected": False,
        "testMode": "local-baseline",
        "message": "ローカルAPIの接続テストは成功しました。契約書PDF取り込みは既存PDF抽出 / Tesseractで動作します。",
        "baselineOcr": {
            "available": bool(ocr.get("available")),
            "engine": ocr.get("engine") or "未検出",
            "pdf": bool(ocr.get("pdf")),
            "image": bool(ocr.get("image")),
            "language": ocr.get("language") or "",
            "missing": ocr.get("missing", []),
        },
    }


def normalize_pdf_import_preview_text(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", cleaned)
    cleaned = cleaned.replace("\r", "")
    cleaned = re.sub(r"[ \t\f\v]+", " ", cleaned)
    cleaned = re.sub(r"\n +", "\n", cleaned)
    cleaned = re.sub(r" +\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\s+([、。，．）」』])", r"\1", cleaned)
    cleaned = re.sub(r"([「『（])\s+", r"\1", cleaned)
    cleaned = re.sub(r"(20\d{2})年\s*(\d{1,2})\s+(\d{1,2})\s*月\s*日付", r"\1年\2月\3日付", cleaned)
    cleaned = re.sub(r"(?<=[ぁ-んァ-ン一-龥]) (?=[ぁ-んァ-ン一-龥])", "", cleaned)
    lines = [line.strip() for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def extract_pdf_page_previews(path: Path, limit: int = 8) -> list[dict[str, object]]:
    count = pdf_page_count(path)
    max_pages = min(count or limit, limit)
    previews: list[dict[str, object]] = []
    for page_number in range(1, max_pages + 1):
        text = normalize_pdf_import_preview_text(extract_pdf_page_text(path, page_number))
        previews.append({
            "page": page_number,
            "textLength": len(text),
            "preview": text[:240].strip(),
        })
    return previews


def contract_pdf_import_try_page_payload(source_path: str, page: object = 1, all_pages: bool = False) -> dict[str, object]:
    cleaned_path = str(source_path or "").strip()
    if not cleaned_path:
        return {"ok": False, "error": "PDFファイルのパスを入力してください。"}
    path = Path(cleaned_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": "PDFファイルが見つかりません。"}
    if path.suffix.lower() != ".pdf":
        return {"ok": False, "error": "PDFファイルを指定してください。"}
    page_number = clamp_pdf_page_number(page)
    text = normalize_pdf_import_preview_text(extract_pdf_text(path) if all_pages else extract_pdf_page_text(path, page_number))
    page_count = pdf_page_count(path) if all_pages else 0
    page_previews = extract_pdf_page_previews(path) if all_pages else []
    preview = text[:1200].strip()
    contract_candidate = extract_contract_candidate("contract-pdf-import", str(path), text) if text else {}
    if contract_candidate:
        contract_candidate["sourceType"] = "contract-pdf-import"
        extraction_json = contract_candidate.get("extractionJson") if isinstance(contract_candidate.get("extractionJson"), dict) else {}
        extraction_json["sourceType"] = "contract-pdf-import"
        contract_candidate["extractionJson"] = extraction_json
    return {
        "ok": True,
        "pdfImportId": "contract-pdf-import",
        "runner": "local-baseline",
        "runnerLabel": "既存PDF抽出 / Tesseract",
        "sourcePath": str(path),
        "page": "all" if all_pages else page_number,
        "allPages": bool(all_pages),
        "pageCount": page_count,
        "pagePreviews": page_previews,
        "pagePreviewsTruncated": bool(page_count and len(page_previews) < page_count),
        "textLength": len(text),
        "preview": preview,
        "contractCandidate": contract_candidate,
        "message": (
            "既存PDF抽出でプレビューを取得しました。"
            if preview
            else "PDFは読めましたが、抽出できる本文がありませんでした。画像PDFの場合は高精度OCR接続後に再試行します。"
        ),
    }


def contract_pdf_import_auto_payload(source_path: str) -> dict[str, object]:
    cleaned_path = str(source_path or "").strip()
    if not cleaned_path:
        return {"ok": False, "error": "PDFファイルのパスを入力してください。"}
    path = Path(cleaned_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": "PDFファイルが見つかりません。"}
    if path.suffix.lower() != ".pdf":
        return {"ok": False, "error": "PDFファイルを指定してください。"}

    page_count = pdf_page_count(path)
    direct_text = normalize_pdf_import_preview_text(
        usable_pdf_text(extract_pdf_text_with_pdftotext(path))
        or usable_pdf_text(extract_pdf_text_with_mdls(path))
    )
    direct_is_good = len(direct_text) >= 120
    method = "pdf-text"
    method_label = "PDFテキスト抽出"
    reason = "PDF内にコピー可能なテキストが見つかりました。OCRは使っていません。"
    text = direct_text
    suggestions: list[dict[str, object]] = []

    if not direct_is_good:
        method = "local-ocr"
        method_label = "既存PDF抽出 / Tesseract OCR"
        reason = "PDFテキストが少ないため、既存抽出とTesseract OCRを試しました。"
        text = normalize_pdf_import_preview_text(extract_pdf_text(path))
        sarashina = sarashina_ocr_status()
        suggestions.append({
            "id": "sarashina2.2-ocr",
            "label": "Sarashina OCR",
            "recommended": bool(sarashina.get("available")),
            "reason": (
                "既存OCRで本文が弱い場合の高精度比較候補です。CPU実行では1ページ数分かかります。"
                if sarashina.get("available")
                else "Sarashina OCRは未準備です。"
            ),
        })
    elif page_count and page_count >= 10:
        suggestions.append({
            "id": "review",
            "label": "原文確認",
            "recommended": True,
            "reason": "ページ数が多いため、抽出後に原文ページで重要項目を確認してください。",
        })

    preview = text[:1600].strip()
    contract_candidate = extract_contract_candidate("contract-pdf-import", str(path), text) if text else {}
    if contract_candidate:
        contract_candidate["sourceType"] = "contract-pdf-import"
        extraction_json = contract_candidate.get("extractionJson") if isinstance(contract_candidate.get("extractionJson"), dict) else {}
        extraction_json["sourceType"] = "contract-pdf-import"
        extraction_json["importMethod"] = method
        extraction_json["importReason"] = reason
        contract_candidate["extractionJson"] = extraction_json
    return {
        "ok": True,
        "pdfImportId": "contract-pdf-import",
        "runner": method,
        "runnerLabel": method_label,
        "sourcePath": str(path),
        "page": "all",
        "allPages": True,
        "pageCount": page_count,
        "textLength": len(text),
        "preview": preview,
        "contractCandidate": contract_candidate,
        "method": method,
        "methodLabel": method_label,
        "reason": reason,
        "suggestions": suggestions,
        "message": (
            "PDF取り込みが完了しました。"
            if preview
            else "PDFは読めましたが、抽出できる本文がありませんでした。詳細OCRを試してください。"
        ),
    }


def contract_document_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "PDF"
    if suffix == ".docx":
        return "Word"
    return suffix.lstrip(".").upper() or "FILE"


def iter_contract_import_documents(root_path: Path) -> list[Path]:
    documents: list[Path] = []
    for current, dirs, filenames in os.walk(root_path):
        dirs[:] = sorted(name for name in dirs if name not in {".git", ".gemma4-data", "__pycache__", "node_modules"} and not name.startswith("."))
        for filename in sorted(filenames):
            path = Path(current) / filename
            if path.suffix.lower() not in CONTRACT_IMPORT_GAP_EXTENSIONS:
                continue
            try:
                info = path.stat()
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                documents.append(path)
    return sorted(documents, key=lambda item: item.relative_to(root_path).as_posix())


def contract_import_gap_payload(root_path: Path | str, folder_id: str, contracts: list[dict] | None = None) -> dict[str, object]:
    root = Path(root_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("フォルダーが見つかりません。")
    records = contracts if contracts is not None else list_contracts(CONTRACT_DB_PATH, folder_id)
    imported_paths = {
        str(Path(str(record.get("sourcePath", ""))).expanduser().resolve())
        for record in records
        if str(record.get("sourcePath", "")).strip()
    }
    imported_rel_paths = {
        str(record.get("sourcePath", "")).strip().replace("\\", "/")
        for record in records
        if str(record.get("sourcePath", "")).strip()
    }
    items: list[dict[str, object]] = []
    imported_count = 0
    for path in iter_contract_import_documents(root):
        relative_path = path.relative_to(root).as_posix()
        resolved_path = str(path.resolve())
        imported = resolved_path in imported_paths or relative_path in imported_rel_paths
        if imported:
            imported_count += 1
            continue
        items.append({
            "path": resolved_path,
            "relativePath": relative_path,
            "kind": contract_document_kind(path),
            "extension": path.suffix.lower(),
            "size": path.stat().st_size,
            "importable": path.suffix.lower() == ".pdf",
        })
    checked = imported_count + len(items)
    return {
        "ok": True,
        "folderId": str(folder_id or ""),
        "root": str(root),
        "checked": checked,
        "imported": imported_count,
        "missing": len(items),
        "items": items,
    }


def workspace_search_capabilities() -> dict[str, object]:
    pdf_backend = ""
    if python_module_available("pypdf"):
        pdf_backend = "pypdf"
    elif shutil.which("pdftotext"):
        pdf_backend = "pdftotext"
    elif shutil.which("mdls"):
        pdf_backend = "Spotlight"
    ocr = ocr_capabilities()
    pdf_available = bool(pdf_backend) or bool(ocr.get("pdf"))
    if not pdf_backend and ocr.get("pdf"):
        pdf_backend = "OCR"
    return {
        "text": True,
        "docx": True,
        "pdf": pdf_available,
        "pdfBackend": pdf_backend,
        "filenameFallback": True,
        "imageOcr": bool(ocr.get("image")),
        "pdfOcr": bool(ocr.get("pdf")),
        "ocr": ocr,
    }


def searchable_workspace_lines(path: Path) -> list[str] | None:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(path).splitlines()
    if suffix == ".pdf":
        return extract_pdf_text(path).splitlines()
    if suffix in OCR_IMAGE_EXTENSIONS:
        text = extract_image_ocr_text(path)
        return text.splitlines() if text else None
    if not is_probably_text(path):
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def extract_knowledge_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def append_workspace_search_result(
    results: list[dict[str, object]],
    seen: set[tuple[str, int]],
    rel: str,
    line_index: int,
    preview: str,
    match_type: str = "body",
    source_kind: str = "text",
) -> bool:
    key = (rel, line_index)
    if key in seen:
        return False
    seen.add(key)
    results.append({
        "path": rel,
        "line": line_index,
        "preview": preview.strip()[:240],
        "matchType": match_type,
        "sourceKind": source_kind,
    })
    return True


def workspace_search_response(
    root_path: Path,
    needle: str,
    needles: list[str],
    results: list[dict[str, object]],
    scanned: int,
    skipped: int,
    truncated: bool,
    pdf_unreadable: int,
) -> dict:
    return {
        "root": str(root_path),
        "query": needle,
        "terms": needles,
        "results": results,
        "scanned": scanned,
        "skipped": skipped,
        "truncated": truncated,
        "pdfUnreadable": pdf_unreadable,
        "pdfBackend": workspace_search_capabilities().get("pdfBackend", ""),
    }


def search_workspace_files(root: str, query: str) -> dict:
    root_path = resolve_workspace_root(root)
    needle = str(query or "").strip()
    if not needle:
        raise ValueError("検索キーワードを入力してください。")
    needles = search_query_terms(needle)
    needle_lowers = [term.lower() for term in needles]
    results: list[dict[str, object]] = []
    scanned = 0
    skipped = 0
    pdf_unreadable = 0
    truncated = False
    seen: set[tuple[str, int]] = set()
    for current, dirs, filenames in os.walk(root_path):
        dirs[:] = sorted(name for name in dirs if name not in IGNORED_DIRS and not name.startswith(".DS_Store"))
        for filename in sorted(filenames):
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
            suffix = path.suffix.lower()
            filename_matches = any(workspace_text_contains_search_term(rel, term) for term in needle_lowers)
            if filename_matches:
                append_workspace_search_result(
                    results,
                    seen,
                    rel,
                    0,
                    "ファイル名に検索語が含まれています。",
                    "filename",
                    suffix.lstrip(".") or "file",
                )
                if len(results) >= MAX_SEARCH_RESULTS:
                    truncated = True
                    return workspace_search_response(root_path, needle, needles, results, scanned, skipped, truncated, pdf_unreadable)
            if info.st_size > MAX_SEARCH_FILE_BYTES:
                skipped += 1
                continue
            lines = searchable_workspace_lines(path)
            if lines is None:
                skipped += 1
                continue
            if suffix == ".pdf" and not lines:
                pdf_unreadable += 1
            scanned += 1
            for line_index, line in enumerate(lines, start=1):
                if not any(workspace_text_contains_search_term(line, term) for term in needle_lowers):
                    continue
                append_workspace_search_result(
                    results,
                    seen,
                    rel,
                    line_index,
                    line,
                    "body",
                    suffix.lstrip(".") or "text",
                )
                if len(results) >= MAX_SEARCH_RESULTS:
                    truncated = True
                    return workspace_search_response(root_path, needle, needles, results, scanned, skipped, truncated, pdf_unreadable)
            if scanned >= MAX_SEARCH_FILES:
                truncated = True
                return workspace_search_response(root_path, needle, needles, results, scanned, skipped, truncated, pdf_unreadable)
    return workspace_search_response(root_path, needle, needles, results, scanned, skipped, truncated, pdf_unreadable)


def language_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".css": "CSS",
        ".html": "HTML",
        ".js": "JavaScript",
        ".jsx": "JavaScript JSX",
        ".mjs": "JavaScript",
        ".py": "Python",
        ".ts": "TypeScript",
        ".tsx": "TypeScript TSX",
        ".vue": "Vue",
        ".svelte": "Svelte",
        ".rs": "Rust",
        ".go": "Go",
        ".swift": "Swift",
        ".java": "Java",
        ".cs": "C#",
        ".php": "PHP",
        ".rb": "Ruby",
    }.get(suffix, suffix.lstrip(".").upper() or "Text")


def extract_code_symbols(text: str, suffix: str) -> list[str]:
    patterns = [
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
        r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b",
        r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(",
        r"^\s*def\s+([A-Za-z_][\w]*)\s*\(",
        r"^\s*class\s+([A-Za-z_][\w]*)\s*[:\(]",
        r"^\s*func\s+([A-Za-z_][\w]*)\s*\(",
        r"^\s*fn\s+([A-Za-z_][\w]*)\s*\(",
    ]
    symbols: list[str] = []
    for line in text.splitlines():
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                name = match.group(1)
                if name not in symbols:
                    symbols.append(name)
                break
        if len(symbols) >= CODEGRAPH_MAX_SYMBOLS_PER_FILE:
            break
    return symbols


def extract_code_imports(text: str) -> list[str]:
    patterns = [
        r"^\s*import\s+(?:.+?\s+from\s+)?[\"']([^\"']+)[\"']",
        r"^\s*export\s+.+?\s+from\s+[\"']([^\"']+)[\"']",
        r"require\(\s*[\"']([^\"']+)[\"']\s*\)",
        r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+",
        r"^\s*import\s+([A-Za-z0-9_\.]+)",
        r"^\s*@import\s+[\"']([^\"']+)[\"']",
    ]
    imports: list[str] = []
    for line in text.splitlines():
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                value = match.group(1)
                if value and value not in imports:
                    imports.append(value)
                break
        if len(imports) >= 24:
            break
    return imports


def build_codegraph_summary(root: str) -> dict:
    root_path = resolve_workspace_root(root)
    files: list[dict[str, object]] = []
    skipped = 0
    total_bytes = 0
    for current, dirs, filenames in os.walk(root_path):
        dirs[:] = sorted(name for name in dirs if name not in IGNORED_DIRS and not name.startswith(".DS_Store"))
        for filename in sorted(filenames):
            if filename == ".DS_Store":
                continue
            path = Path(current) / filename
            suffix = path.suffix.lower()
            if suffix not in CODEGRAPH_EXTENSIONS:
                continue
            try:
                info = path.stat()
            except OSError:
                skipped += 1
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_size > CODEGRAPH_MAX_FILE_BYTES:
                skipped += 1
                continue
            if not is_probably_text(path):
                skipped += 1
                continue
            rel = path.relative_to(root_path).as_posix()
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                skipped += 1
                continue
            total_bytes += info.st_size
            files.append({
                "path": rel,
                "language": language_for_path(path),
                "size": info.st_size,
                "symbols": extract_code_symbols(content, suffix),
                "imports": extract_code_imports(content),
            })
            if len(files) >= CODEGRAPH_MAX_FILES:
                skipped += 1
                break
        if len(files) >= CODEGRAPH_MAX_FILES:
            break
    summary = {
        "version": 1,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rootName": root_path.name,
        "stats": {
            "files": len(files),
            "skipped": skipped,
            "bytes": total_bytes,
        },
        "files": files,
    }
    storage = "workspace"
    output_dir = root_path / CODEGRAPH_DIR_NAME
    output_path = output_dir / CODEGRAPH_SUMMARY_FILE
    try:
        output_dir.mkdir(exist_ok=True)
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as workspace_error:
        storage = "app"
        output_path = codegraph_cache_path(root_path)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as cache_error:
            raise ValueError(
                "コード理解の解析結果を保存できませんでした。"
                f"対象フォルダーとアプリ管理フォルダーの書き込み権限を確認してください: {workspace_error}; {cache_error}"
            ) from cache_error
    return {
        "root": str(root_path),
        "path": f"{CODEGRAPH_DIR_NAME}/{CODEGRAPH_SUMMARY_FILE}" if storage == "workspace" else str(output_path),
        "storage": storage,
        "summary": summary,
    }


def read_codegraph_summary(root: str) -> dict:
    root_path = resolve_workspace_root(root)
    summary_path = root_path / CODEGRAPH_DIR_NAME / CODEGRAPH_SUMMARY_FILE
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    cache_path = codegraph_cache_path(root_path)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    raise ValueError("コード理解はまだ準備されていません。フォルダー編集で「準備する」を押してください。")


def read_workspace_file(root: str, relative_path: str) -> dict:
    path = resolve_workspace_file(root, relative_path)
    if not path.exists() or not path.is_file():
        raise ValueError("file does not exist")
    size = path.stat().st_size
    suffix = path.suffix.lower()
    if suffix in SEARCHABLE_DOCUMENT_EXTENSIONS:
        if size > MAX_DOCUMENT_CONTEXT_BYTES:
            raise ValueError(f"document is too large to read ({size} bytes)")
        if suffix == ".docx":
            content = extract_docx_text(path)
        else:
            content = extract_pdf_text(path)
        if not content.strip():
            if suffix == ".pdf":
                ocr = ocr_capabilities()
                missing = " / ".join(str(item) for item in ocr.get("missing", []) or [])
                raise ValueError(
                    "PDF本文を読み取れませんでした。画像だけのPDFや文字化けするPDFはOCRが必要です。"
                    f"OCRプラグインのために {missing or 'Tesseract / Poppler'} を導入してください。"
                )
            raise ValueError("document text could not be extracted")
        return {
            "path": relative_path,
            "size": size,
            "content": content,
        }
    if suffix in OCR_IMAGE_EXTENSIONS:
        if size > MAX_DOCUMENT_CONTEXT_BYTES:
            raise ValueError(f"image is too large to read with OCR ({size} bytes)")
        content = extract_image_ocr_text(path)
        if not content.strip():
            raise ValueError("OCR text could not be extracted. Install Tesseract or choose a clearer image.")
        return {
            "path": relative_path,
            "size": size,
            "content": content,
        }
    if size > MAX_FILE_BYTES:
        raise ValueError(f"file is too large to read in UI ({size} bytes)")
    if not is_probably_text(path):
        raise ValueError("file does not look like text")
    return {
        "path": relative_path,
        "size": size,
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


def read_attached_file(name: str, mime: str, payload_base64: str) -> dict:
    safe_name = Path(name or "attachment").name
    if not payload_base64:
        raise ValueError("attachment data is empty")
    try:
        raw = base64.b64decode(payload_base64, validate=True)
    except binascii.Error as exc:
        raise ValueError("attachment data is invalid") from exc
    size = len(raw)
    if size > MAX_ATTACHMENT_BYTES:
        raise ValueError(f"attachment is too large ({size} bytes)")
    suffix = Path(safe_name).suffix.lower()
    kind = "PDF" if suffix == ".pdf" or mime == "application/pdf" else "DOCX" if suffix == ".docx" else "TEXT"
    if suffix in {".txt", ".md", ".markdown"} or str(mime).startswith("text/"):
        content = raw.decode("utf-8", errors="replace")
        return {"name": safe_name, "kind": kind, "size": size, "content": content}
    if suffix not in {".pdf", ".docx"} and mime != "application/pdf":
        raise ValueError("unsupported attachment type")
    with tempfile.NamedTemporaryFile(suffix=suffix or ".pdf", delete=False) as handle:
        handle.write(raw)
        temp_path = Path(handle.name)
    try:
        content = extract_docx_text(temp_path) if suffix == ".docx" else extract_pdf_text(temp_path)
        if not content.strip():
            if suffix == ".pdf" or mime == "application/pdf":
                ocr = ocr_capabilities()
                missing = " / ".join(str(item) for item in ocr.get("missing", []) or [])
                if ocr.get("pdf"):
                    raise ValueError(
                        "PDF本文を読み取れませんでした。画像だけのPDFや文字がつぶれたPDFの可能性があります。"
                        "必要なら「設定」→「プラグイン」→「画像文字読み取り（OCR）」を確認してください。"
                    )
                raise ValueError(
                    "PDF本文を読み取れませんでした。画像だけのPDFを読むにはOCRが必要です。"
                    "「設定」→「プラグイン」→「画像文字読み取り（OCR）」を追加またはセットアップしてください。"
                    f"不足: {missing or 'Tesseract / Poppler'}"
                )
            raise ValueError("添付ファイルの本文を読み取れませんでした。別形式で保存し直すか、テキストとして貼り付けてください。")
        return {"name": safe_name, "kind": kind, "size": size, "content": content}
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def write_workspace_file(root: str, relative_path: str, content: str) -> dict:
    if not relative_path or relative_path.endswith("/"):
        raise ValueError("relative file path is required")
    path = resolve_workspace_file(root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": path.relative_to(resolve_workspace_root(root)).as_posix(), "size": len(content.encode("utf-8"))}


def reveal_workspace_path(root: str, relative_path: str) -> dict:
    root_path = resolve_workspace_root(root)
    path = resolve_workspace_file(root, relative_path) if relative_path else root_path
    target = path if path.exists() else path.parent
    if not target.exists():
        target = root_path
    if sys.platform == "darwin":
        args = ["open", "-R", str(path)] if path.exists() else ["open", str(target)]
    elif sys.platform.startswith("win"):
        args = ["explorer", f"/select,{path}"] if path.exists() else ["explorer", str(target)]
    else:
        args = ["xdg-open", str(target if target.is_dir() else target.parent)]
    subprocess.Popen(args)
    return {"path": path.relative_to(root_path).as_posix() if path != root_path else "", "opened": str(target)}


SCRIPT_RE = re.compile(r"<script(?:\s[^>]*)?>(.*?)</script>", re.IGNORECASE | re.DOTALL)
EXTERNAL_ASSET_RE = re.compile(
    r"<(?:script|link|img|iframe|audio|video|source)\b[^>]*(?:src|href)\s*=\s*[\"']https?://",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"(?:TODO|FIXME|ここに|省略|以下省略|同様に|実装してください|\\.\\.\\.|…)",
    re.IGNORECASE,
)


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
            encoding="utf-8",
            errors="replace",
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
    if content.lstrip().startswith(relative_path):
        errors.append("File path appears inside the file content.")
    if PLACEHOLDER_RE.search(content):
        errors.append("Content appears to include TODO, omitted code, or placeholder text.")
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
        if EXTERNAL_ASSET_RE.search(content):
            errors.append("HTML uses external assets. Use a self-contained file unless the user explicitly asks otherwise.")
        if content.lower().count("<script") != content.lower().count("</script>"):
            errors.append("HTML script tag count does not match.")
        if content.lower().count("<style") != content.lower().count("</style>"):
            errors.append("HTML style tag count does not match.")
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
    if workspace.get("codegraph"):
        try:
            summary = read_codegraph_summary(str(root_path))
            files = summary.get("files", []) if isinstance(summary, dict) else []
            stats = summary.get("stats", {}) if isinstance(summary, dict) else {}
            graph_lines = [
                "",
                "--- CODE UNDERSTANDING SUMMARY ---",
                "Use this summary to understand project structure. Treat file paths and symbols here as local workspace evidence.",
                "When answering code questions, mention the relevant file path when it helps. Do not invent files or functions that are not in the summary or selected files.",
                f"Analyzed files: {stats.get('files', len(files))}, skipped: {stats.get('skipped', 0)}",
            ]
            for item in files[:30]:
                if not isinstance(item, dict):
                    continue
                details = []
                symbols = item.get("symbols") if isinstance(item.get("symbols"), list) else []
                imports = item.get("imports") if isinstance(item.get("imports"), list) else []
                if symbols:
                    details.append("symbols: " + ", ".join(str(value) for value in symbols[:8]))
                if imports:
                    details.append("imports: " + ", ".join(str(value) for value in imports[:8]))
                detail = f" ({'; '.join(details)})" if details else ""
                graph_lines.append(f"- {item.get('path', '')} [{item.get('language', '')}]{detail}")
            if len(files) > 30:
                graph_lines.append(f"- ... {len(files) - 30} more files")
            parts.append("\n".join(graph_lines))
        except Exception as exc:
            parts.append(f"\n--- CODE UNDERSTANDING SUMMARY ---\n[Not ready: {exc}]")
    search_query = str(workspace.get("searchQuery") or "").strip()
    if search_query:
        try:
            use_knowledge = bool(workspace.get("knowledge")) and bool(str(workspace.get("folderId", "")).strip())
            search_data = search_knowledge(
                db_path=KNOWLEDGE_DB_PATH,
                folder_id=str(workspace.get("folderId", "")).strip(),
                query=search_query,
                limit=8,
            ) if use_knowledge else search_workspace_files(str(root_path), search_query)
            results = search_data.get("results", [])
            result_count = len(results) if isinstance(results, list) else 0
            if use_knowledge:
                records = knowledge_result_to_records(
                    search_data,
                    scope_type="folder",
                    scope_id=str(workspace.get("folderId", "")).strip(),
                    owner_type="user",
                    owner_id="local-user",
                    project_id=str(workspace.get("projectId", "") or ""),
                )
                context_data = build_local_context(
                    records,
                    query=search_query,
                    scope={"scopeType": "folder", "scopeId": str(workspace.get("folderId", "")).strip()},
                    limit=8,
                )
                search_lines = [
                    "",
                    "--- 資料検索結果 ---",
                    str(context_data.get("text") or ""),
                    f"ヒット数: {result_count}件 / SQLite索引",
                ]
                if not result_count:
                    search_lines.append("- 一致する文字は見つかりませんでした。")
                parts.append("\n".join(line for line in search_lines if line))
            else:
                search_lines = [
                    "",
                    "--- フォルダー内検索結果 ---",
                    (
                        "以下はユーザーのフォルダー内を検索した結果です。回答するときは、この結果から分かることだけを短く答えてください。"
                        "本文一致の根拠は `path:line`、ファイル名一致の根拠は `path` だけで示してください。"
                        "複数候補がある場合は、候補を2〜4件に絞って短い理由を並べてください。"
                        "検索結果にない内容は推測せず、見つからないと伝えてください。"
                    ),
                    f"検索語: {search_query}",
                    f"ヒット数: {result_count}件 / 調査したファイル: {search_data.get('scanned', 0)}件 / スキップ: {search_data.get('skipped', 0)}件",
                ]
                for item in results[:12]:
                    if not isinstance(item, dict):
                        continue
                    path_value = item.get("path", "")
                    if item.get("matchType") == "filename":
                        search_lines.append(f"- {path_value} (ファイル名一致) {item.get('preview', '')}")
                    else:
                        search_lines.append(f"- {path_value}:{item.get('line', '')} {item.get('preview', '')}")
                if search_data.get("truncated"):
                    search_lines.append("- 結果が多いため一部だけ表示しています。")
                if not result_count:
                    search_lines.append("- 一致する文字は見つかりませんでした。")
                parts.append("\n".join(search_lines))
        except Exception as exc:
            parts.append(f"\n--- フォルダー内検索結果 ---\n[検索に失敗しました: {exc}]")
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


def context_memory_list_payload(query: dict[str, object]) -> dict[str, object]:
    include_inactive = str(query.get("includeInactive") or "").lower() in {"1", "true", "yes"}
    records = list_context_records(
        CONTEXT_DB_PATH,
        scope={
            "scopeType": str(query.get("scopeType") or ""),
            "scopeId": str(query.get("scopeId") or ""),
        },
        include_inactive=include_inactive,
    )
    return {
        "ok": True,
        "records": [record.to_dict() for record in records],
    }


def context_memory_profile_payload(query: dict[str, object]) -> dict[str, object]:
    scope = {
        "scopeType": str(query.get("scopeType") or ""),
        "scopeId": str(query.get("scopeId") or ""),
    }
    records = list_context_records(CONTEXT_DB_PATH, scope=scope)
    return context_profile(records, scope=scope)


def context_memory_save_payload(body: dict[str, object]) -> dict[str, object]:
    item = body.get("item") if isinstance(body.get("item"), dict) else body
    scope = body.get("scope") if isinstance(body.get("scope"), dict) else {
        "scopeType": body.get("scopeType", ""),
        "scopeId": body.get("scopeId", ""),
        "ownerType": body.get("ownerType", "user"),
        "ownerId": body.get("ownerId", "local"),
        "projectId": body.get("projectId", ""),
    }
    result = remember(item if isinstance(item, dict) else {}, scope=scope)
    if not result.get("ok"):
        return result
    save_context_record(CONTEXT_DB_PATH, result["record"])
    return result


def context_memory_forget_payload(body: dict[str, object]) -> dict[str, object]:
    record_id = str(body.get("id") or "").strip()
    if not record_id:
        return {"ok": False, "error": "id is required"}
    return forget_context_record(CONTEXT_DB_PATH, record_id, reason=str(body.get("reason") or ""))


def context_memory_update_payload(body: dict[str, object]) -> dict[str, object]:
    record_id = str(body.get("id") or "").strip()
    if not record_id:
        return {"ok": False, "error": "id is required"}
    updates = body.get("updates") if isinstance(body.get("updates"), dict) else body
    return update_context_record(CONTEXT_DB_PATH, record_id, updates if isinstance(updates, dict) else {})


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


QWEN3_2507_MODEL = "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL"
AGENTIC_CODER_MODEL = "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M"


def run_sysctl_value(name: str) -> str:
    if sys.platform != "darwin":
        return ""
    try:
        result = subprocess.run(
            ["sysctl", "-n", name],
            check=False,
            capture_output=True,
            timeout=2,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return decode_subprocess_output(result.stdout).strip()


def local_memory_gb() -> int:
    value = run_sysctl_value("hw.memsize")
    try:
        return max(0, round(int(value) / (1024 ** 3)))
    except (TypeError, ValueError):
        return 0


def local_cpu_name() -> str:
    value = run_sysctl_value("machdep.cpu.brand_string")
    if value:
        return value
    machine = platform.machine() or ""
    processor = platform.processor() or ""
    return " ".join(part for part in [processor, machine] if part).strip() or "不明"


def local_pc_system_info(available_models: set[str] | list[str] | None = None, ollama_version: str = "") -> dict[str, object]:
    cpu_name = local_cpu_name()
    machine = platform.machine() or ""
    is_apple_silicon = sys.platform == "darwin" and machine.lower() in {"arm64", "aarch64"}
    gpu_name = "Apple Silicon GPU" if is_apple_silicon else ""
    models = sorted(str(model) for model in (available_models or []) if model)
    return {
        "os": platform.platform() or sys.platform,
        "cpu": cpu_name,
        "machine": machine,
        "memoryGb": local_memory_gb(),
        "gpu": gpu_name,
        "hasGpu": bool(gpu_name),
        "isAppleSilicon": is_apple_silicon,
        "ollamaVersion": ollama_version,
        "availableModels": models,
    }


def pc_diagnostics_recommendation(system_info: dict[str, object]) -> dict[str, object]:
    memory_gb = int(system_info.get("memoryGb") or 0)
    is_apple_silicon = bool(system_info.get("isAppleSilicon"))
    available = {str(model) for model in system_info.get("availableModels") or []}
    has_mlx = "gemma4:12b-mlx" in available
    has_agentic = AGENTIC_CODER_MODEL in available

    if memory_gb >= 24 and (is_apple_silicon or has_mlx):
        level = "comfortable"
        label = "快適"
        summary = "このPCでは12B系も使いやすいです。標準はGemma 4 MLX、コードはAgentic Coderを優先できます。"
        standard = "gemma4:12b-mlx"
        coding = AGENTIC_CODER_MODEL if has_agentic else "gemma4:12b-mlx"
        warnings: list[str] = []
    elif memory_gb >= 12:
        level = "heavy"
        label = "重い"
        summary = "軽量モデル中心がおすすめです。12B系は必要な時だけ使うと安定します。"
        standard = QWEN3_2507_MODEL
        coding = AGENTIC_CODER_MODEL if has_agentic else "gemma4:12b-mlx"
        warnings = ["12B系は応答が重くなる可能性があります。"]
    else:
        level = "very-heavy"
        label = "激重い"
        summary = "軽いモデル中心がおすすめです。12B系や実験モデルは避ける方が安定します。"
        standard = "qwen2.5:3b"
        coding = QWEN3_2507_MODEL
        warnings = ["12B系、HauhauCS、実験モデルはこのPCでは非推奨です。"]

    return {
        "level": level,
        "label": label,
        "summary": summary,
        "recommended": {
            "standard": standard,
            "coding": coding,
            "light": QWEN3_2507_MODEL,
            "translation": "qwen2.5:3b",
        },
        "warnings": warnings,
    }


def pc_diagnostics_payload(available_models: set[str] | list[str] | None = None, ollama_version: str = "") -> dict[str, object]:
    system_info = local_pc_system_info(available_models=available_models, ollama_version=ollama_version)
    return {
        "ok": True,
        "system": system_info,
        "recommendation": pc_diagnostics_recommendation(system_info),
    }


AGENT_REACH_PRIMARY_COMMAND = "agent-reach"
AGENT_REACH_COMMAND_CANDIDATES = [AGENT_REACH_PRIMARY_COMMAND, "agentreach"]
INTERNET_LAYER_RESULT_SCHEMA_VERSION = "tomos-internet-layer-result-v0.1"
AGENT_REACH_INSTALL_GUIDE_URL = "https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md"
AGENT_REACH_DOCTOR_TIMEOUT_SECONDS = 15
AGENT_REACH_VENV_DIR = Path.home() / ".agent-reach-venv"
AGENT_REACH_PACKAGE_URL = "git+https://github.com/Panniantong/Agent-Reach.git"
YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS = 45
YOUTUBE_TRANSCRIPT_MAX_CHARS = 12000
YOUTUBE_YTDLP_CLIENT_ARGS = ["--extractor-args", "youtube:player_client=android,android_vr"]
YOUTUBE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?[^ \n\r\t]+|shorts/[^ \n\r\t]+|live/[^ \n\r\t]+)|youtu\.be/[^ \n\r\t]+)",
    re.IGNORECASE,
)
WEB_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
WEB_READER_TIMEOUT_SECONDS = 15
WEB_READER_MAX_CHARS = 80000
WEB_ORIGIN_MAX_BYTES = 2 * 1024 * 1024
COMPLETE_LIST_PROMPT_MAX_CHARS = 6000
GITHUB_REPO_RE = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", re.IGNORECASE)
GITHUB_TIMEOUT_SECONDS = 20
RSS_TIMEOUT_SECONDS = 15
RSS_MAX_ITEMS = 5
COMMUNITY_TIMEOUT_SECONDS = 15


def agent_reach_venv_python() -> Path:
    return AGENT_REACH_VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def agent_reach_venv_executable() -> Path:
    return AGENT_REACH_VENV_DIR / ("Scripts/agent-reach.exe" if os.name == "nt" else "bin/agent-reach")


def agent_reach_venv_ytdlp_command() -> list[str]:
    venv_python = agent_reach_venv_python()
    if venv_python.exists():
        return [str(venv_python), "-m", "yt_dlp"]
    resolved = shutil.which("yt-dlp")
    return [resolved] if resolved else []


def agent_reach_executable() -> str:
    venv_executable = agent_reach_venv_executable()
    if venv_executable.exists():
        return str(venv_executable)
    for command in AGENT_REACH_COMMAND_CANDIDATES:
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return ""


def agent_reach_command_contract(executable: str = "") -> dict[str, object]:
    command = executable or AGENT_REACH_PRIMARY_COMMAND
    return {
        "tool": "Agent-Reach",
        "schemaVersion": INTERNET_LAYER_RESULT_SCHEMA_VERSION,
        "installGuideUrl": AGENT_REACH_INSTALL_GUIDE_URL,
        "doctorCommand": [command, "doctor", "--json"],
        "executionMode": "upstream-tools",
        "executionPolicy": {
            "autoInstall": False,
            "requiresUserConfirmation": True,
            "autoSaveToMemory": False,
            "snsRequiresExplicitPermission": True,
        },
        "resultShape": {
            "ok": "boolean",
            "query": "string",
            "channel": "web|github|youtube|rss|sns",
            "summary": "string",
            "sources": [{"title": "string", "url": "string", "snippet": "string"}],
            "warnings": ["string"],
        },
    }


def extract_youtube_urls(text: str, limit: int = 2) -> list[str]:
    urls: list[str] = []
    for match in YOUTUBE_URL_RE.finditer(str(text or "")):
        url = match.group(0).rstrip(").,、。]")
        if url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def extract_web_urls(text: str, limit: int = 3) -> list[str]:
    urls: list[str] = []
    youtube_urls = set(extract_youtube_urls(text, limit=10))
    for match in WEB_URL_RE.finditer(str(text or "")):
        url = match.group(0).rstrip(").,、。]")
        if url in youtube_urls or "youtube.com/" in url or "youtu.be/" in url or "github.com/" in url:
            continue
        if url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def extract_github_repos(text: str, limit: int = 3) -> list[str]:
    repos: list[str] = []
    for match in GITHUB_REPO_RE.finditer(str(text or "")):
        owner = match.group(1).strip("/")
        repo = match.group(2).strip("/").removesuffix(".git")
        name = f"{owner}/{repo}"
        if name not in repos:
            repos.append(name)
        if len(repos) >= limit:
            break
    return repos


def should_auto_use_external_research(query: str) -> bool:
    normalized = str(query or "").strip()
    if not normalized:
        return False
    has_supported_url = bool(
        extract_youtube_urls(normalized, limit=1)
        or extract_github_repos(normalized, limit=1)
        or extract_web_urls(normalized, limit=1)
    )
    if not has_supported_url:
        return False
    return bool(re.search(
        r"分析|調べ|調査|要約|解説|説明|見て|読んで|確認|評価|比較|まとめ|analy[sz]e|summari[sz]e|explain|review|check|research",
        normalized,
        re.IGNORECASE,
    ))


def should_read_search_result_pages(query: str) -> bool:
    normalized = str(query or "").strip()
    if not normalized:
        return False
    if re.search(
        r"すべて|一覧|箇条書き|網羅|complete list|all (?:series|works|items)",
        normalized,
        re.IGNORECASE,
    ):
        return True
    list_suffix = r"(?=$|アップ|[\s、。,.，．・:：;；!?！？/／「」『』（）()\[\]【】]|(?:は|が|を|に|へ|で|と|の|も|や|か|から|まで|より|だけ|しか|でも|って))"
    if re.search(rf"(?<![ァ-ヶー])リスト{list_suffix}", normalized):
        return True
    request_pattern = rf"(?:教えて|出して|書いて|見せて|一覧|箇条書き|(?<![ァ-ヶー])リスト{list_suffix}|網羅)"
    standalone_boundaries = "、。,.，．・:：;；!?！？/／「」『』（）()[]【】はがをにへでとのもやか"
    for marker in re.finditer(r"全(?:部|て|件)", normalized):
        left_ok = marker.start() == 0 or normalized[marker.start() - 1].isspace() or normalized[marker.start() - 1] in standalone_boundaries
        tail = normalized[marker.end():]
        right_ok = not tail or tail[0].isspace() or tail[0] in standalone_boundaries or re.match(request_pattern, tail)
        if left_ok and right_ok:
            return True
    enumerable_targets = (
        "キャラクター", "エピソード", "バージョン", "シリーズ", "タイトル", "メンバー",
        "アルバム", "イベント", "商品", "製品", "項目", "記事", "候補", "種類", "モデル",
        "プラン", "機能", "店舗", "楽曲", "映画", "動画", "ゲーム", "書籍", "型番", "名称",
        "作品", "機種", "話", "曲", "巻", "章", "回",
    )
    target_pattern = "|".join(re.escape(target) for target in enumerable_targets)
    for candidate in re.finditer(rf"全(?:{target_pattern})", normalized):
        if candidate.start() > 0 and normalized[candidate.start() - 1] in "安完":
            continue
        tail = normalized[candidate.end():candidate.end() + 24]
        if re.search(rf"^[^。！？\n]{{0,16}}{request_pattern}", tail):
            return True
    return False


def should_buffer_complete_list_stream(
    use_web_search: bool,
    query: str,
    channels: list[str] | tuple[str, ...] = (),
    results: list[dict[str, str]] | tuple[dict[str, str], ...] = (),
) -> bool:
    if not use_web_search or not should_read_search_result_pages(query):
        return False
    if extract_youtube_urls(query, limit=1) or extract_github_repos(query, limit=1):
        return False
    specialized_channels = {"youtube", "github", "rss", "v2ex", "bilibili", "sns"}
    if any(str(channel or "").strip().lower() in specialized_channels for channel in channels):
        return False
    for result in results:
        source = str(result.get("source") or "").strip().lower()
        if source.startswith("agent-reach:") and source != "agent-reach:web":
            return False
    return True


def emit_or_buffer_chat_chunk(chunk, buffer_output, parts, emit) -> None:
    if not chunk:
        return
    parts.append(chunk)
    if not buffer_output:
        emit(chunk)


def web_result_priority_score(result: dict[str, str], index: int = 0) -> tuple[int, int]:
    title = str(result.get("title") or "").lower()
    url = str(result.get("url") or "").lower()
    score = 50
    authority_band = complete_list_authority_band(url)
    if authority_band == 0:
        score -= 45
    if authority_band == 1:
        score -= 22
    if any(marker in url for marker in ("wiki", "dictionary", "encyclopedia")):
        score -= 12
    if any(marker in title for marker in ("公式", "official", "一覧", "インデックス", "list")):
        score -= 8
    if any(marker in url for marker in ("blog", "note.", "note.com", "matome", "まとめ")):
        score += 10
    return score, index


def extract_list_followup_links(page_result: dict[str, str], limit: int = 8) -> list[str]:
    base_url = str(page_result.get("url") or "").strip()
    snippet = str(page_result.get("snippet") or "")
    if not base_url or not snippet:
        return []
    parsed_base = urllib.parse.urlparse(base_url)
    if not parsed_base.netloc:
        return []
    base_path = parsed_base.path.rstrip("/")
    base_parent = base_path.rsplit("/", 1)[0] if "/" in base_path else ""
    base_name = base_path.rsplit("/", 1)[-1]
    found: list[tuple[str, str]] = []
    markdown_link_re = re.compile(r"\[([^\]]{1,80})\]\((https?://[^)\s]+|/[^)\s]+)\)")
    raw_url_re = re.compile(r"https?://[^\s<>)]+")
    for match in markdown_link_re.finditer(snippet):
        found.append((match.group(1), urllib.parse.urljoin(base_url, match.group(2))))
    for match in raw_url_re.finditer(snippet):
        found.append(("", match.group(0)))

    links: list[str] = []
    seen: set[str] = {base_url}
    for label, url in found:
        clean_url = url.strip().rstrip(".,。)")
        parsed = urllib.parse.urlparse(clean_url)
        if parsed.netloc != parsed_base.netloc:
            continue
        if re.search(r"\.(?:jpe?g|png|gif|webp|svg|avif|ico)(?:$|\?)", parsed.path, re.IGNORECASE):
            continue
        text = f"{label} {clean_url}".lower()
        candidate_path = parsed.path.rstrip("/")
        candidate_parent = candidate_path.rsplit("/", 1)[0] if "/" in candidate_path else ""
        candidate_name = candidate_path.rsplit("/", 1)[-1]
        explicit_pagination = bool(re.search(r"次|続|一覧|インデックス|ページ|page|list|module", text, re.IGNORECASE))
        same_sequence = bool(
            candidate_parent == base_parent
            and re.fullmatch(r"\d{2}[_-]\d+", base_name)
            and re.fullmatch(r"\d{2}[_-]\d+", candidate_name)
        )
        if not explicit_pagination and not same_sequence:
            continue
        normalized_url = urllib.parse.urlunparse(parsed._replace(fragment=""))
        if normalized_url in seen:
            continue
        seen.add(normalized_url)
        links.append(normalized_url)
        if len(links) >= limit:
            break
    return links


def augment_search_results_with_page_text(
    query: str,
    results: list[dict[str, str]],
    reader=None,
    limit: int = 3,
    followup_limit: int = 8,
) -> tuple[list[dict[str, str]], str]:
    if not should_read_search_result_pages(query) or not results:
        return results, ""
    if reader is None:
        reader = web_reader_result
    augmented = list(results)
    errors: list[str] = []
    attempt_count = 0
    read_count = 0
    seen_urls = {str(result.get("url") or "").strip() for result in augmented}
    prioritized_results = [
        result for _, result in sorted(
            enumerate(results),
            key=lambda pair: web_result_priority_score(pair[1], pair[0]),
        )
    ]
    for result in prioritized_results:
        url = str(result.get("url") or "").strip()
        if not url or not url.startswith(("http://", "https://")):
            continue
        attempt_count += 1
        try:
            page_result = reader(url)
            if page_result:
                page_url = str(page_result.get("url") or url).strip()
                if page_url not in seen_urls:
                    augmented.append(page_result)
                    seen_urls.add(page_url)
                else:
                    augmented.append(page_result)
                read_count += 1
        except Exception as exc:
            errors.append(f"Web本文取得: {exc}")
        if attempt_count >= max(1, limit):
            break
    return augmented, " / ".join(errors)


def normalized_fact_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"[「」『』（）()【】\[\]<>〈〉《》]", "", text)
    text = re.sub(r"[\s　:：・,，、。.!！?？/／\-―ー_※*＊`]+", "", text)
    return text.lower()


def source_text_for_results(results: list[dict[str, str]]) -> str:
    return "\n".join(
        part
        for result in results
        for part in (
            str(result.get("title") or ""),
            str(result.get("snippet") or ""),
        )
        if part
    )


def list_item_supported_by_sources(item: str, source_text: str) -> bool:
    candidate = re.sub(r"^[\s>*\-・•]+", "", str(item or "")).strip()
    candidate = re.sub(r"^\d+[.)．、]\s*", "", candidate).strip()
    candidate = candidate.strip("*` ")
    if not candidate:
        return True
    if len(candidate) <= 3:
        return True
    source_norm = normalized_fact_text(source_text)
    candidate_norm = normalized_fact_text(candidate)
    if candidate_norm and candidate_norm in source_norm:
        return True
    base = re.split(r"[（(【\[]", candidate, maxsplit=1)[0].strip()
    base_norm = normalized_fact_text(base)
    return bool(base_norm and len(base_norm) >= 4 and base_norm in source_norm)


def remove_unverified_list_items(content: str, query: str, results: list[dict[str, str]]) -> str:
    if not should_read_search_result_pages(query) or not results:
        return content
    source_text = source_text_for_results(results)
    if not source_text.strip():
        return content
    removed: list[str] = []
    kept_lines: list[str] = []
    bullet_re = re.compile(r"^(\s*)([*\-・•]|\d+[.)．、])\s+(.+?)\s*$")
    for line in str(content or "").splitlines():
        match = bullet_re.match(line)
        if not match:
            kept_lines.append(line)
            continue
        item = match.group(3).strip()
        if list_item_supported_by_sources(item, source_text):
            kept_lines.append(line)
        else:
            removed.append(item)
    filtered = "\n".join(kept_lines).strip()
    if removed:
        note = "出典本文で確認できない項目は除外しました。"
        if "## 確認できていない点" in filtered:
            filtered = f"{filtered}\n- {note}"
        else:
            filtered = f"{filtered}\n\n## 確認できていない点\n- {note}"
    return filtered or content


def complete_list_intents(query: str) -> frozenset[str]:
    text = str(query or "")
    intents = set()
    for intent, pattern in {
        "game": r"ゲーム|game",
        "book": r"漫画|マンガ|書籍|小説|comic|manga|book|novel",
        "product": r"商品|模型|玩具|グッズ|model|toy|goods",
        "series": r"アニメ|映像作品|TV|OVA|劇場|配信|anime",
    }.items():
        if re.search(pattern, text, re.IGNORECASE):
            intents.add(intent)
    if not intents and re.search(r"シリーズ|series", text, re.IGNORECASE):
        intents.add("series")
    return frozenset(intents or {"generic"})


def complete_list_heading_label(heading: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", str(heading or "")).strip()
    link_match = re.fullmatch(r"\[([^\]]+)\]\((?:https?://|/)[^)]+\)", text)
    if link_match:
        text = link_match.group(1).strip()
    return re.sub(r"^(?:\*\*|__)(.+?)(?:\*\*|__)$", r"\1", text).strip()


def complete_list_heading_categories(heading: str) -> frozenset[str]:
    label = re.sub(r"\s+", "", complete_list_heading_label(heading)).lower()
    if label == "ゲーム関連書籍":
        return frozenset({"game", "book"})
    if label == "その他の映像作品":
        return frozenset({"series", "other"})

    aliases = {
        "series": {
            "シリーズ", "映像", "映像作品", "映像シリーズ", "アニメ", "アニメ作品", "アニメシリーズ",
            "tv", "tv作品", "tvシリーズ", "テレビ", "テレビ作品", "テレビシリーズ",
            "ova", "ova作品", "ovaシリーズ", "劇場", "劇場作品", "劇場シリーズ", "劇場版",
            "映画", "映画作品", "映画シリーズ", "配信", "配信作品", "配信シリーズ",
            "series", "anime", "animeworks", "animeseries", "video", "videos", "videoworks", "videoseries",
            "tvworks", "tvseries", "ovaworks", "ovaseries", "movie", "movies", "movieworks", "movieseries",
            "film", "films", "filmworks", "filmseries", "streaming", "streamingworks", "streamingseries",
        },
        "game": {
            "ゲーム", "ゲーム作品", "ゲームシリーズ", "テレビゲーム", "tvゲーム",
            "game", "games", "gameworks", "gameseries", "videogame", "videogames", "videogameworks", "videogameseries",
        },
        "book": {
            "漫画", "漫画作品", "漫画シリーズ", "マンガ", "マンガ作品", "マンガシリーズ",
            "書籍", "書籍作品", "書籍シリーズ", "小説", "小説作品", "小説シリーズ",
            "comic", "comics", "comicworks", "comicseries", "manga", "mangaworks", "mangaseries",
            "book", "books", "bookworks", "bookseries", "novel", "novels", "novelworks", "novelseries",
        },
        "product": {
            "商品", "商品作品", "商品シリーズ", "模型", "模型作品", "模型シリーズ",
            "玩具", "玩具作品", "玩具シリーズ", "グッズ", "グッズ作品", "グッズシリーズ",
            "product", "products", "productworks", "productseries", "model", "models", "modelworks", "modelseries",
            "toy", "toys", "toyworks", "toyseries", "goods", "merchandise",
        },
        "other": {"その他", "その他の作品", "音楽", "実写", "舞台", "ラジオ", "other", "music", "liveaction", "stage", "radio"},
    }
    return frozenset(category for category, values in aliases.items() if label in values)


def complete_list_is_category_heading(heading: str) -> bool:
    return bool(complete_list_heading_categories(heading))


def complete_list_is_excluded_heading(heading: str) -> bool:
    label = re.sub(r"\s+", "", complete_list_heading_label(heading)).lower()
    return bool(re.search(
        r"脚注|注釈|出典|参考文献|関連項目|外部リンク|ログイン|アカウント作成|footnotes?|references?|externallinks?|relateditems?|login|sign[-_]?in|sign[-_]?up",
        label,
        re.IGNORECASE,
    ))


def complete_list_section_allowed(query: str, headings: list[str]) -> bool:
    if any(complete_list_is_excluded_heading(heading) for heading in headings or []):
        return False

    intents = complete_list_intents(query)
    requested = set(intents) & {"series", "game", "book", "product"}
    if not requested:
        return True

    categories = set()
    for heading in headings or []:
        categories.update(complete_list_heading_categories(heading))
    if not categories:
        return True
    return bool(categories & requested) and categories <= requested


def clean_grounded_list_candidate(raw: str) -> str:
    item = str(raw or "").strip()
    if not item:
        return ""
    item = re.sub(r"^(?:[*\-・•]|\d+[.)．、])\s*", "", item).strip()
    heading_match = re.match(r"^#{1,6}\s+(.+)$", item)
    if heading_match:
        item = heading_match.group(1).strip()
        if not re.fullmatch(r"\[[^\]]+\]\((?:https?://|/)[^)]+\)", item):
            return ""
    if item.startswith(("![", "[![")):
        return ""
    markdown_link_match = re.fullmatch(r"\[([^\]]+)\]\((?:https?://|/)[^)]+\)", item)
    if markdown_link_match:
        item = markdown_link_match.group(1).strip()
    item = re.sub(r"^(?:\*\*|__)(.+?)(?:\*\*|__)$", r"\1", item).strip()
    item = re.sub(r"^[●○◯]\s*", "", item)
    item = re.sub(r"^(?:Webページ本文|YouTube動画|動画タイトル|Title)\s*[:：]\s*", "", item).strip()
    item = item.strip(" -・•*`　。、")
    item = re.sub(r"\s+", " ", item)
    if not (4 <= len(item) <= 48):
        return ""
    generic_terms = {
        "ガンダム",
        "ガンダムシリーズ",
        "ガンダム作品",
        "ガンダムゲーム全般",
        "sdガンダムシリーズ",
    }
    if normalized_fact_text(item) in {normalized_fact_text(term) for term in generic_terms}:
        return ""
    if re.search(r"^(published time|markdown content|title|url|source|snippet|出典|脚注|注釈|関連項目|概要)\s*[:：]?", item, re.IGNORECASE):
        return ""
    if re.search(r"wikipedia|フリー百科事典|記事のポイント|情報源", item, re.IGNORECASE):
        return ""
    if re.fullmatch(r"【[^】]{1,16}】(?:全\d+(?:話|本|巻|冊))?", item, re.IGNORECASE):
        return ""
    if re.fullmatch(r"全\d+(?:話|本|巻|冊)", item, re.IGNORECASE):
        return ""
    if re.fullmatch(r"\d{4}(?:年)?(?:[-/]\d{1,2}(?:[-/]\d{1,2})?)?", item):
        return ""
    if re.fullmatch(r"(?:19|20)\d{2}年代(?:順|目次)?", item):
        return ""
    if re.fullmatch(r"(?:全|第)?\d+(?:話|本|巻|冊|回|期)", item):
        return ""
    if re.match(r"^(?:監督|会社|制作|製作|放送局|配給|公開日|発売日|ナビゲーション)\s*(?:[:：]|$)", item):
        return ""
    if re.fullmatch(
        r"(?:(?:公式|最新)?(?:ニュース|お知らせ|情報|チャンネル|サイト|ホーム|トップ|メニュー|ログイン|検索|次へ|前へ)(?:一覧|情報|ページ|リンク)?|(?:official\s+)?(?:news|notice|announcements?|channel|site|home|top|menu|login|search|next|previous))",
        item,
        re.IGNORECASE,
    ):
        return ""
    if re.search(r"youtube|チャンネル|channel", item, re.IGNORECASE):
        return ""
    if re.search(r"^(?:取得メタデータ|メタデータ|metadata|content)\s*[:：]", item, re.IGNORECASE):
        return ""
    if re.search(r"\.(?:jpe?g|png|gif|webp|svg)(?:\?.*)?$", item, re.IGNORECASE):
        return ""
    if re.fullmatch(r"MODULE\.\d+\s*//?", item, re.IGNORECASE):
        return ""
    if any(marker in item for marker in ("http://", "https://", "一覧", "全体", "あらすじ", "公式サイト", "ページ")):
        return ""
    if re.search(r"[。！？!?]|[、,].{4,}|(?:です|ます|でした|しました|されています|とは|について|は、|は )", item):
        return ""
    if item.endswith(("など", "全般", "一部")):
        return ""
    return item


def grounded_list_candidate_category(item: str) -> str:
    text = str(item or "")
    if re.search(r"ゲーム|game|アプリ|mobile|switch|playstation|xbox|steam|ソフト", text, re.IGNORECASE):
        return "ゲーム"
    if re.search(r"漫画|マンガ|コミック|小説|書籍|本|novel|comic|manga|book", text, re.IGNORECASE):
        return "書籍・漫画・小説"
    if re.search(r"模型|プラモデル|フィギュア|玩具|商品|グッズ|カード|toy|figure|model|goods|merch", text, re.IGNORECASE):
        return "商品・模型"
    if re.search(r"【(?:TV|配信|映画|劇場|OVA|Web|WEB)】|全\d+話|劇場版|映画|配信|TV|テレビ|アニメ|動画|video|movie|film|anime|ova", text, re.IGNORECASE):
        return "映像・放送・配信"
    return "未分類"


def extract_grounded_list_candidates_from_results(
    results: list[dict[str, str]], query: str = "", limit: int | None = None
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for result in results:
        snippet = str(result.get("snippet") or "")
        headings: list[str] = []
        for line in snippet.splitlines():
            heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
            heading_categories: frozenset[str] = frozenset()
            if heading_match:
                level = len(heading_match.group(1))
                heading = heading_match.group(2).strip()
                heading_categories = complete_list_heading_categories(heading)
                linked_heading = bool(re.fullmatch(r"\[[^\]]+\]\((?:https?://|/)[^)]+\)", heading))
                update_state = not linked_heading or bool(heading_categories) or complete_list_is_excluded_heading(heading)
                if level == 1:
                    headings = []
                elif level == 2 and update_state:
                    headings = [heading]
                elif level == 3 and update_state:
                    headings = headings[:1] + [heading]
            if not complete_list_section_allowed(query, headings):
                continue
            if heading_match and complete_list_is_category_heading(heading):
                continue
            cells = structured_candidate_cells(line)
            for cell in cells:
                item = clean_grounded_list_candidate(cell)
                if not item:
                    continue
                key = normalized_fact_text(item)
                if not key or key in seen:
                    continue
                seen.add(key)
                candidates.append(item)
                if limit is not None and len(candidates) >= limit:
                    return candidates
    return candidates


@dataclass(frozen=True)
class CompleteListEvidence:
    query: str
    source_domain: str
    source_results: tuple[dict[str, str], ...]
    candidates: tuple[str, ...]
    status: str
    warnings: tuple[str, ...]


def complete_list_host(value: str) -> str:
    parsed = urllib.parse.urlparse(value if "://" in value else f"//{value}")
    return (parsed.hostname or "").rstrip(".").lower()


def complete_list_authority_band(domain: str) -> int:
    host = complete_list_host(domain)
    labels = host.split(".")
    suffix = ".".join(labels[-2:])
    registrable = labels[-3] if suffix in {"co.jp", "ne.jp", "or.jp", "ac.jp", "com.au", "co.uk", "org.uk"} and len(labels) >= 3 else labels[-2] if len(labels) >= 2 else ""
    if host.endswith(".go.jp") or host.endswith(".gov") or host.endswith(".edu") or registrable == "official" or registrable.endswith("-official"):
        return 0
    if host == "wikipedia.org" or host.endswith(".wikipedia.org"):
        return 1
    return 2


def complete_list_source_groups(results: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    groups: dict[str, dict[str, object]] = {}
    for order, result in enumerate(results):
        title = str(result.get("title") or "")
        source = str(result.get("source") or "")
        url = str(result.get("url") or "")
        if not (title.startswith("Webページ本文:") or source == "agent-reach:web"):
            continue
        if re.search(r"ログイン|アカウント作成|login|sign.?up|url短縮|youtube playlist", f"{title} {url}", re.I):
            continue
        domain = complete_list_host(url)
        if domain:
            group = groups.setdefault(domain, {"order": order, "results": []})
            group["results"].append(result)
    return groups


def rank_complete_list_sources(
    groups: dict[str, dict[str, object]], query: str = ""
) -> list[tuple[str, list[dict[str, str]], list[str]]]:
    ranked: list[tuple[str, list[dict[str, str]], list[str], int, int]] = []
    for domain, group in groups.items():
        source_results = group["results"]
        candidates = extract_grounded_list_candidates_from_results(source_results, query=query)
        if candidates:
            ranked.append((domain, source_results, candidates, complete_list_authority_band(domain), group["order"]))
    trusted = [item for item in ranked if item[3] <= 1]
    return [item[:3] for item in sorted(trusted, key=lambda item: (item[3], -len(item[2]), item[4]))]


def structured_candidate_cells(line: str) -> list[str]:
    stripped = line.strip()
    if re.match(r"^(?:[*\-・•]|\d+[.)．、])\s+", stripped):
        return [stripped]
    if re.match(r"^#{1,6}\s+\[[^\]]+\]\((?:https?://|/)[^)]+\)$", stripped):
        return [stripped]
    if re.fullmatch(r"\[(?!\!)[^\]]+\]\((?:https?://|/)[^)]+\)", stripped):
        return [stripped]
    if re.fullmatch(r"(?:\*\*|__).*?(?:\*\*|__)", stripped):
        return [stripped]
    if "|" in stripped and not re.fullmatch(r"[|:\-\s]+", stripped):
        cells = [cell.strip() for cell in stripped.split("|") if cell.strip()]
        links = [cell for cell in cells if re.search(r"\[[^\]]+\]\((?:https?://|/)[^)]+\)", cell)]
        if links:
            return links[:1]
        return [cell for cell in cells if clean_grounded_list_candidate(cell)][:1]
    return []


def build_complete_list_evidence(query: str, results: list[dict[str, str]]) -> CompleteListEvidence:
    ranked = rank_complete_list_sources(complete_list_source_groups(results), query=query)
    if not ranked:
        return CompleteListEvidence(query, "", (), (), "unavailable", ("根拠ページ本文を取得できませんでした。",))
    domain, source_results, candidates = ranked[0]
    status = "source-backed" if len(candidates) >= 3 else "partial" if candidates else "unavailable"
    unique_sources = tuple({result["url"]: result for result in source_results if result.get("url") and extract_grounded_list_candidates_from_results([result], query=query)}.values())
    warnings = ("候補が100件を超えたため、100件まで表示します。",) if len(candidates) > 100 else ()
    return CompleteListEvidence(query, domain, unique_sources, tuple(candidates[:100]), status, warnings)


def complete_list_intro(system_prompt: str) -> str:
    text = str(system_prompt or "")
    rejects_politeness = re.search(
        r"(?:敬語|丁寧(?:語)?|です[・･]?ます(?:調)?)(?:は|を|に)?(?:なし|使わない|使わず|ではなく|じゃなく(?:て)?|避け|しない|禁止|不要)",
        text,
    )
    ending = "まとめました。" if not rejects_politeness and re.search(r"敬語|丁寧|です[・･]?ます", text) else "まとめたよ。"
    def setting(pattern: str) -> str:
        match = re.search(pattern, text)
        value = match.group(1).strip() if match else ""
        return value if re.fullmatch(r"[A-Za-z0-9ぁ-んァ-ヶ一-龯ー]{1,24}", value) else ""
    user_name = setting(r"ユーザーの呼び方は「([^」\n]{1,24})」です。")
    self_name = setting(r"自分自身を指すときは「([^」\n]{1,24})」を")
    if user_name and self_name:
        return f"{user_name}、{self_name}が確認できた内容を{ending}"
    if user_name:
        return f"{user_name}、確認できた内容を{ending}"
    return f"{self_name}が確認できた内容を{ending}" if self_name else f"確認できた内容を{ending}"


def render_complete_list_answer(system_prompt: str, evidence: CompleteListEvidence) -> str:
    intro = complete_list_intro(system_prompt)
    if evidence.status == "unavailable":
        return f"{intro}\n\n## 確認できていない点\n- 一覧項目を抽出できませんでした。対象ページのURLを指定して再度お試しください。"
    lines = [intro, "", f"## 確認できた項目（{len(evidence.candidates)}件）"]
    lines.extend(f"- {item}" for item in evidence.candidates)
    note = "完全な一覧としては確認できませんでした。" if evidence.status == "partial" else "取得した根拠ページで確認できた項目だけを掲載しています。"
    lines.extend(["", "## 確認できていない点", f"- {note}"])
    lines.extend(f"- {warning}" for warning in evidence.warnings)
    return "\n".join(lines)


def public_search_results_for_answer(results, evidence):
    return list(evidence.source_results) if evidence else results


def complete_list_diagnostic(evidence: CompleteListEvidence) -> dict[str, object]:
    status = "success" if evidence.status == "source-backed" else "warning" if evidence.status == "partial" else "error"
    if evidence.status == "unavailable":
        message = "一覧の根拠ページを確認できませんでした。"
    elif evidence.status == "partial":
        message = "根拠ページから一部の項目を確認しました。完全な一覧ではありません。"
    else:
        message = f"単一の根拠ドメインから{len(evidence.candidates)}件を確認しました。"
    return {
        "type": "complete-list-grounding",
        "status": status,
        "label": "一覧根拠",
        "message": message,
        "sourceDomain": evidence.source_domain,
        "sourceCount": len(evidence.source_results),
        "candidateCount": len(evidence.candidates),
        "mode": "deterministic-complete-list",
    }


def finalize_complete_list_answer(system_prompt, results, evidence):
    return (
        render_complete_list_answer(system_prompt, evidence),
        public_search_results_for_answer(results, evidence),
        complete_list_diagnostic(evidence),
    )


def categorize_grounded_list_candidates(candidates: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in candidates:
        category = grounded_list_candidate_category(item)
        grouped.setdefault(category, []).append(item)
    return grouped


def select_complete_list_grounding_results(
    results: list[dict[str, str]], query: str = "", minimum_candidates: int = 3
) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = {}
    first_indexes: dict[str, int] = {}
    for index, result in enumerate(results):
        title = str(result.get("title") or "")
        source = str(result.get("source") or "")
        if not title.startswith("Webページ本文:") and source != "agent-reach:web":
            continue
        url = str(result.get("url") or "").strip()
        domain = complete_list_host(url)
        if not domain:
            continue
        groups.setdefault(domain, []).append(result)
        first_indexes.setdefault(domain, index)

    eligible: list[tuple[tuple[int, int], list[dict[str, str]]]] = []
    for domain, grouped_results in groups.items():
        candidates = extract_grounded_list_candidates_from_results(
            grouped_results, query=query, limit=minimum_candidates
        )
        if len(candidates) < minimum_candidates:
            continue
        best_score = min(
            web_result_priority_score(result, first_indexes[domain])
            for result in grouped_results
        )
        eligible.append((best_score, grouped_results))
    if not eligible:
        return results
    eligible.sort(key=lambda item: item[0])
    return eligible[0][1]


def build_search_context_for_query(query: str, results: list[dict[str, str]]) -> str:
    if not should_read_search_result_pages(query):
        return build_search_context(results)
    if not results:
        return build_search_context(results)

    grounding_results = select_complete_list_grounding_results(results, query=query)
    lines = [
        "Web search results follow. Use only the verified candidate strings and sources below.",
        "Do not invent or complete missing names from memory.",
        "Verified candidate strings:",
    ]
    candidates = extract_grounded_list_candidates_from_results(grounding_results, query=query, limit=100)
    for item in candidates:
        candidate_line = f"- {item}"
        if len("\n".join([*lines, candidate_line])) > COMPLETE_LIST_PROMPT_MAX_CHARS - 800:
            break
        lines.append(candidate_line)

    lines.extend(["", "Sources:"])
    for index, result in enumerate(grounding_results[:10], start=1):
        title = str(result.get("title") or "").strip()
        url = str(result.get("url") or "").strip()
        source_line = f"[{index}] {title} | {url}"
        if len("\n".join([*lines, source_line])) > COMPLETE_LIST_PROMPT_MAX_CHARS:
            break
        lines.append(source_line)

    if not candidates:
        lines.extend(["", "Retrieved excerpts:"])
        for result in grounding_results[:3]:
            snippet = str(result.get("snippet") or "").strip()[:1200]
            if not snippet:
                continue
            if len("\n".join([*lines, snippet])) > COMPLETE_LIST_PROMPT_MAX_CHARS:
                break
            lines.append(snippet)
    return "\n".join(lines)[:COMPLETE_LIST_PROMPT_MAX_CHARS].strip()


def is_empty_generated_category_heading(line: str) -> bool:
    stripped = str(line or "").strip()
    if not stripped.startswith("## "):
        return False
    heading = stripped.lstrip("#").strip()
    return heading in {"映像・放送・配信", "ゲーム", "書籍・漫画・小説", "商品・模型", "未分類"}


def organize_mixed_list_categories(content: str, query: str, results: list[dict[str, str]]) -> str:
    if not should_read_search_result_pages(query) or not results:
        return content
    grounding_results = select_complete_list_grounding_results(results, query=query)
    candidates = extract_grounded_list_candidates_from_results(grounding_results, query=query)
    if not candidates:
        return content
    known_categories = categorize_grounded_list_candidates(candidates)
    if len([category for category, items in known_categories.items() if category != "未分類" and items]) < 2:
        return content

    lines = str(content or "").splitlines()
    bullet_re = re.compile(r"^(\s*)([*\-・•]|\d+[.)．、])\s+(.+?)\s*$")
    grouped: dict[str, list[str]] = {}
    kept_non_bullets: list[str] = []
    in_confirmed_section = False
    saw_confirmed_heading = False
    for line in lines:
        stripped = line.strip()
        if is_empty_generated_category_heading(line):
            continue
        if stripped.startswith("## "):
            if "確認できた項目" in stripped:
                in_confirmed_section = True
                saw_confirmed_heading = True
                kept_non_bullets.append(line)
                continue
            if saw_confirmed_heading:
                in_confirmed_section = False
        match = bullet_re.match(line)
        if (in_confirmed_section or not saw_confirmed_heading) and match:
            item = match.group(3).strip()
            cleaned_item = clean_grounded_list_candidate(item)
            if not cleaned_item:
                continue
            item = cleaned_item
            category = grounded_list_candidate_category(item)
            if category == "未分類":
                return content
            grouped.setdefault(category, []).append(f"- {item}")
            continue
        kept_non_bullets.append(line)

    ordered_categories = ["映像・放送・配信", "ゲーム", "書籍・漫画・小説", "商品・模型"]
    active_categories = [category for category in ordered_categories if grouped.get(category)]
    if len([category for category in active_categories if category != "未分類"]) < 2:
        return content

    output: list[str] = []
    inserted = False
    for line in kept_non_bullets:
        output.append(line)
        if not inserted and line.strip().startswith("## ") and "確認できた項目" in line:
            for category in active_categories:
                output.append("")
                output.append(f"### {category}")
                output.extend(grouped[category])
            inserted = True
    if not inserted:
        output.append("")
        output.append("## 確認できた項目")
        for category in active_categories:
            output.append("")
            output.append(f"### {category}")
            output.extend(grouped[category])
    return "\n".join(output).strip()


def complete_list_grounding_instruction(query: str, results: list[dict[str, str]], error: str = "") -> str:
    if not should_read_search_result_pages(query) or not results:
        return ""
    source_text = source_text_for_results(results).strip()
    if not source_text:
        return ""
    parts = [
        "一覧系Web調査回答ルール:",
        "- これは完全一覧・箇条書き系の質問です。",
        "- 回答はWeb調査結果の本文に文字として明示された項目だけにしてください。",
        "- 直前のAI回答、一般知識、推測、連想で項目を増やさないでください。",
        "- 見出し、カテゴリ名、途中で切れた断片を作品名や固有名詞として扱わないでください。",
        "- 出典本文で確認できない箇条書き項目は書かないでください。",
        "- 複数カテゴリが混ざる場合は、ひとつの一覧に混ぜずカテゴリ別に分けてください。",
        "- 完全性を確認できない場合は、最後に「確認できていない点」として短く書いてください。",
        "- 通常のマイキャラの口調、呼びかけ、言い回しを維持してください。",
    ]
    if error:
        parts.append("- 取得エラーがある場合も、取得済みの出典本文だけを根拠にしてください。")
    grounding_results = select_complete_list_grounding_results(results, query=query)
    candidates = extract_grounded_list_candidates_from_results(grounding_results, query=query)
    if candidates:
        grouped = categorize_grounded_list_candidates(candidates)
        if len([category for category in grouped if category != "未分類"]) > 1:
            parts.append("")
            parts.append("カテゴリ分離ルール:")
            parts.append("- 確認済み候補に複数カテゴリがあるため、回答ではカテゴリごとに分けてください。")
            for category in ("映像・放送・配信", "ゲーム", "書籍・漫画・小説", "商品・模型", "未分類"):
                items = grouped.get(category)
                if not items:
                    continue
                parts.append(f"- {category}")
    return "\n".join(parts)


def auto_internet_layer_channels_for_query(query: str) -> list[str]:
    diagnostics = internet_layer_diagnostics_payload()
    channels = diagnostics.get("channels", {}) if isinstance(diagnostics, dict) else {}

    def channel_ready(name: str) -> bool:
        value = channels.get(name) if isinstance(channels, dict) else {}
        return isinstance(value, dict) and value.get("status") == "ready"

    selected: list[str] = []
    if extract_youtube_urls(query, limit=1) and channel_ready("youtube"):
        selected.append("youtube")
    if extract_github_repos(query, limit=1) and channel_ready("github"):
        selected.append("github")
    if extract_web_urls(query, limit=1) and channel_ready("web"):
        selected.append("web")
    return selected


def external_research_answer_instruction(results: list[dict[str, str]], error: str = "") -> str:
    if not results:
        return ""
    parts = [
        "Web調査回答ルール:",
        "- Web調査の出典があるため、「Web調査をONにしてください」とは案内しないでください。",
        "- 取得できたタイトル、説明欄、字幕抜粋、検索スニペットだけを根拠として分析してください。",
        "- 出典に文字として出てこない作品名、人名、会社名、日付、数値、箇条書き項目は追加しないでください。",
        "- 「全件」「一覧」「すべて」などの依頼では、ページ本文が取得できていない場合は完全な一覧として断定しないでください。",
        "- 字幕本文やページ本文が不足している場合は、分析の冒頭ではなく最後に「確認できていない点」として短く書いてください。",
        "- 動画URLの分析では、動画タイトル、説明欄、字幕抜粋があれば内容の要点、論点、注意点を分けて答えてください。",
        "- 根拠にない事実、発言、数値、結論は作らないでください。",
    ]
    if error:
        parts.append("- 取得エラーがある場合も、取得済みの出典があればその範囲で回答してください。")
    return "\n".join(parts)


def external_research_diagnostics(query: str, channels: list[str], results: list[dict[str, str]], error: str = "") -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    if not extract_youtube_urls(query, limit=1):
        return diagnostics
    youtube_results = [result for result in results if str(result.get("source") or "") == "agent-reach:youtube"]
    has_transcript = any("字幕抜粋:" in str(result.get("snippet") or "") for result in youtube_results)
    if has_transcript:
        diagnostics.append({
            "type": "youtube-transcript",
            "status": "success",
            "label": "YouTube字幕取得",
            "message": "成功。字幕本文を使って分析しています。",
            "howToSucceed": "この状態なら動画内容の要約・論点整理に使えます。",
        })
        return diagnostics
    if youtube_results:
        diagnostics.append({
            "type": "youtube-transcript",
            "status": "warning",
            "label": "YouTube字幕取得",
            "message": "未取得。タイトルまたは説明欄だけを使っています。",
            "howToSucceed": "動画に字幕があるか、時間をおいて再送信してください。字幕がない動画は深い分析ができません。",
        })
        return diagnostics
    if "youtube" not in channels:
        diagnostics.append({
            "type": "youtube-transcript",
            "status": "warning",
            "label": "YouTube字幕取得",
            "message": "未実行。Web調査のYouTube字幕ルートに入っていません。",
            "howToSucceed": "Web調査をONにして、YouTube URLと「分析して」「要約して」などの依頼を同じ文に入れてください。",
        })
        return diagnostics
    diagnostics.append({
        "type": "youtube-transcript",
        "status": "error",
        "label": "YouTube字幕取得",
        "message": "失敗。字幕本文を取得できませんでした。",
        "howToSucceed": "Web調査診断でYouTube字幕が利用可能か確認し、時間をおいて再送信してください。YouTube側のbot判定や字幕未公開で失敗することがあります。",
        "error": "YouTube字幕を取得できませんでした。",
    })
    return diagnostics


ROUTE_BACKEND_LABELS = {
    "jina": "Jina",
    "exa": "Exa",
    "youtube": "YouTube字幕",
    "github": "GitHub",
    "rss": "RSS",
    "tomos": "TOMOS標準検索",
}
ROUTE_BACKEND_ALIASES = {
    "jina reader": "jina",
    "yt-dlp": "youtube",
    "gh cli": "github",
    "feedparser": "rss",
}
ROUTE_ERROR_CODES = {"priority-failed", "fallback-failed", "route-failed"}


def route_diagnostic(
    channel: str,
    backend: str,
    fallback: bool = False,
    route_reason: str = "",
    error_code: str = "",
) -> dict[str, object]:
    backend_key = str(backend or "tomos").strip().lower()
    backend_key = ROUTE_BACKEND_ALIASES.get(backend_key, backend_key)
    if backend_key not in ROUTE_BACKEND_LABELS:
        backend_key = "tomos"
    backend_label = ROUTE_BACKEND_LABELS[backend_key]
    safe_error_code = error_code if error_code in ROUTE_ERROR_CODES else ""

    if safe_error_code == "fallback-failed":
        status = "error"
        message = f"{backend_label}とTOMOS標準検索で結果を取得できませんでした。"
        how_to_succeed = "時間をおいて再送信してください。"
    elif fallback:
        status = "warning"
        message = f"{backend_label}からTOMOS標準検索へ切り替えました。"
        how_to_succeed = "優先経路が使えなかったため、TOMOS標準検索で確認しています。"
    elif safe_error_code == "route-failed":
        status = "error"
        message = f"{backend_label}で確認できませんでした。"
        how_to_succeed = "時間をおいて再送信してください。"
    else:
        status = "success"
        message = f"{backend_label}を使用しました。"
        how_to_succeed = "利用可能な経路で確認しています。"

    return {
        "type": "route",
        "status": status,
        "label": "使用経路",
        "message": message,
        "howToSucceed": how_to_succeed,
        "channel": str(channel or ""),
        "backend": backend_label,
        "fallback": bool(fallback),
        "errorCode": safe_error_code,
    }


def direct_external_research_answer(query: str, results: list[dict[str, str]], error: str = "") -> str:
    if not should_auto_use_external_research(query) or not results:
        return ""
    primary = results[0]
    title = str(primary.get("title") or "Web調査結果").strip()
    url = str(primary.get("url") or "").strip()
    snippet = str(primary.get("snippet") or "").strip()
    transcript_match = re.search(r"字幕抜粋:\s*(.+)", snippet, re.S)
    has_transcript_excerpt = bool(transcript_match and transcript_match.group(1).strip())
    if has_transcript_excerpt:
        return ""
    unconfirmed_points: list[str] = []
    if not has_transcript_excerpt:
        unconfirmed_points.append("- 字幕本文を取得できていないため、動画内の具体的な発言内容は未確認です。")
    if error:
        unconfirmed_points.append(f"- 取得時の制限: {error}")
    lines = [
        "Web調査で確認できた範囲で分析します。",
        "",
        "## 確認できた情報",
        f"- 出典: {title}",
    ]
    if url:
        lines.append(f"- URL: {url}")
    if "動画タイトル:" in snippet:
        for line in snippet.splitlines():
            if line.startswith("動画タイトル:"):
                lines.append(f"- {line}")
                break
    elif snippet:
        lines.append(f"- 抜粋: {snippet[:240]}")
    lines.extend([
        "",
        "## 分析",
        "- 取得できた情報だけを見る限り、この動画は上記タイトルに関する話題を扱っています。",
        "- タイトルや検索結果から主題は推測できますが、動画内で実際に話された詳細、根拠、時系列、結論までは断定できません。",
        "- そのため、内容の深い要約や発言単位の分析には字幕または本文取得が必要です。",
    ])
    if unconfirmed_points:
        lines.extend(["", "## 確認できていない点", *unconfirmed_points])
    return "\n".join(lines)


def clean_youtube_vtt_text(text: str, max_chars: int = YOUTUBE_TRANSCRIPT_MAX_CHARS) -> str:
    lines: list[str] = []
    previous = ""
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.upper().startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if line.lower().startswith(("kind:", "language:")):
            continue
        if "-->" in line or re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&[a-zA-Z0-9#]+;", " ", line)
        line = " ".join(line.split())
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
        if sum(len(item) + 1 for item in lines) >= max_chars:
            break
    return "\n".join(lines)[:max_chars].strip()


def youtube_transcript_from_metadata(metadata: dict, opener=urllib.request.urlopen) -> str:
    caption_sets: list[dict] = []
    for key in ("subtitles", "automatic_captions"):
        value = metadata.get(key) if isinstance(metadata, dict) else {}
        if isinstance(value, dict):
            caption_sets.append(value)
    language_priority = ["ja", "ja-JP", "en", "zh-Hans", "zh-Hant"]
    candidates: list[dict] = []
    for captions in caption_sets:
        for language in language_priority:
            entries = captions.get(language)
            if isinstance(entries, list):
                candidates.extend(entry for entry in entries if isinstance(entry, dict))
        for language, entries in captions.items():
            if str(language).startswith("ja") and isinstance(entries, list):
                candidates.extend(entry for entry in entries if isinstance(entry, dict))
    seen_urls: set[str] = set()
    for entry in candidates:
        url = str(entry.get("url") or "").strip()
        ext = str(entry.get("ext") or "").strip().lower()
        if not url or url in seen_urls or (ext and ext != "vtt"):
            continue
        seen_urls.add(url)
        try:
            with opener(url, timeout=WEB_READER_TIMEOUT_SECONDS) as response:
                text = decode_subprocess_output(response.read())
            transcript = clean_youtube_vtt_text(text)
            if transcript:
                return transcript
        except Exception:
            continue
    return ""


def clean_reader_text(text: str, max_chars: int = WEB_READER_MAX_CHARS) -> str:
    cleaned = "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())
    return cleaned[:max_chars].strip()


class EmbeddedTitleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.capture_tag = ""
        self.capture_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = tag.lower()
        if normalized == "strong" or re.fullmatch(r"h[1-6]", normalized):
            self.capture_tag = normalized
            self.capture_parts = []

    def handle_data(self, data: str) -> None:
        if self.capture_tag:
            self.capture_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized != self.capture_tag:
            return
        text = re.sub(r"\s+", " ", "".join(self.capture_parts)).strip()
        if text:
            if normalized == "strong":
                self.lines.append(f"**{text}**")
            else:
                self.lines.append(f"{'#' * int(normalized[1])} {text}")
        self.capture_tag = ""
        self.capture_parts = []


def extract_next_f_embedded_html(raw_html: str, max_chars: int = WEB_READER_MAX_CHARS) -> str:
    embedded_strings: list[str] = []

    def collect_strings(value) -> None:
        if isinstance(value, str):
            if "<" in value and ">" in value:
                embedded_strings.append(value)
            return
        if isinstance(value, list):
            for item in value:
                collect_strings(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                collect_strings(item)

    prefix = "self.__next_f.push("
    for script in SCRIPT_RE.findall(str(raw_html or "")):
        source = script.strip()
        if not source.startswith(prefix) or not source.endswith(")"):
            continue
        try:
            collect_strings(json.loads(source[len(prefix):-1]))
        except (json.JSONDecodeError, TypeError):
            continue

    lines: list[str] = []
    seen: set[str] = set()
    for fragment in embedded_strings:
        parser = EmbeddedTitleHTMLParser()
        try:
            parser.feed(fragment)
            parser.close()
        except Exception:
            continue
        for line in parser.lines:
            key = normalized_fact_text(line)
            if not key or key in seen:
                continue
            seen.add(key)
            lines.append(line)
            if sum(len(item) + 1 for item in lines) >= max_chars:
                return "\n".join(lines)[:max_chars].strip()
    return "\n".join(lines)[:max_chars].strip()


def is_safe_public_web_url(url: str, resolver=socket.getaddrinfo) -> bool:
    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.port not in (None, 443):
        return False
    try:
        addresses = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror):
        return False
    resolved = []
    for address in addresses:
        try:
            resolved.append(ipaddress.ip_address(address[4][0]))
        except (IndexError, ValueError):
            return False
    return bool(resolved) and all(address.is_global for address in resolved)


class NoWebRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def read_public_origin_html(url: str) -> str:
    if not is_safe_public_web_url(url):
        return ""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 TOMOS-AI/1.0"},
    )
    opener = urllib.request.build_opener(NoWebRedirectHandler())
    with opener.open(request, timeout=WEB_READER_TIMEOUT_SECONDS) as response:
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "text/html" not in content_type:
            return ""
        raw = response.read(WEB_ORIGIN_MAX_BYTES + 1)
    if len(raw) > WEB_ORIGIN_MAX_BYTES:
        return ""
    return raw.decode("utf-8", errors="replace")


def reader_text_may_hide_embedded_titles(text: str) -> bool:
    return len(re.findall(r"!\[[^\]]*\]\([^)]*\)", str(text or ""))) >= 2


def web_reader_result(
    url: str,
    opener=urllib.request.urlopen,
    origin_reader=None,
) -> dict[str, str] | None:
    reader_url = f"https://r.jina.ai/{url}"
    request = urllib.request.Request(
        reader_url,
        headers={"User-Agent": "Mozilla/5.0 TOMOS-AI/1.0"},
    )
    with opener(request, timeout=WEB_READER_TIMEOUT_SECONDS) as response:
        text = response.read().decode("utf-8", errors="replace")
    cleaned = clean_reader_text(text)
    if not cleaned:
        return None
    if reader_text_may_hide_embedded_titles(cleaned) and complete_list_authority_band(url) == 0:
        try:
            raw_html = (origin_reader or read_public_origin_html)(url)
            embedded = extract_next_f_embedded_html(raw_html)
            if embedded:
                cleaned = clean_reader_text(f"{embedded}\n\n{cleaned}")
        except Exception:
            pass
    title = url
    for line in cleaned.splitlines()[:8]:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip() or title
            break
    return {
        "title": f"Webページ本文: {title}",
        "url": url,
        "snippet": cleaned,
        "source": "agent-reach:web",
    }


def github_repo_result(repo: str, runner=subprocess.run) -> dict[str, str] | None:
    command = [
        "gh",
        "repo",
        "view",
        repo,
        "--json",
        "nameWithOwner,description,url,stargazerCount,primaryLanguage",
    ]
    result = runner(command, check=False, capture_output=True, timeout=GITHUB_TIMEOUT_SECONDS)
    if getattr(result, "returncode", 1) != 0:
        raise RuntimeError(decode_subprocess_output(getattr(result, "stderr", "")) or "GitHubリポジトリ情報を取得できませんでした。")
    payload = json.loads(decode_subprocess_output(getattr(result, "stdout", "")) or "{}")
    name = str(payload.get("nameWithOwner") or repo)
    description = str(payload.get("description") or "")
    language = payload.get("primaryLanguage") or {}
    language_name = language.get("name") if isinstance(language, dict) else ""
    stars = payload.get("stargazerCount")
    snippet = "\n".join(
        item for item in [
            f"リポジトリ: {name}",
            f"説明: {description}" if description else "",
            f"主な言語: {language_name}" if language_name else "",
            f"スター数: {stars}" if stars is not None else "",
        ] if item
    )
    return {
        "title": f"GitHubリポジトリ: {name}",
        "url": str(payload.get("url") or f"https://github.com/{repo}"),
        "snippet": snippet,
        "source": "agent-reach:github",
    }


def github_search_results(query: str, runner=subprocess.run, limit: int = 5) -> list[dict[str, str]]:
    command = [
        "gh",
        "search",
        "repos",
        query,
        "--sort",
        "stars",
        "--limit",
        str(max(1, min(limit, 10))),
        "--json",
        "fullName,description,url,stargazersCount",
    ]
    result = runner(command, check=False, capture_output=True, timeout=GITHUB_TIMEOUT_SECONDS)
    if getattr(result, "returncode", 1) != 0:
        raise RuntimeError(decode_subprocess_output(getattr(result, "stderr", "")) or "GitHub検索に失敗しました。")
    payload = json.loads(decode_subprocess_output(getattr(result, "stdout", "")) or "[]")
    results: list[dict[str, str]] = []
    for item in payload if isinstance(payload, list) else []:
        name = str(item.get("fullName") or item.get("url") or "GitHub")
        description = str(item.get("description") or "")
        stars = item.get("stargazersCount")
        results.append({
            "title": f"GitHub検索: {name}",
            "url": str(item.get("url") or ""),
            "snippet": "\n".join(part for part in [
                f"リポジトリ: {name}",
                f"説明: {description}" if description else "",
                f"スター数: {stars}" if stars is not None else "",
            ] if part),
            "source": "agent-reach:github",
        })
    return [item for item in results if item["url"]]


def xml_text(element: ET.Element | None, names: list[str]) -> str:
    if element is None:
        return ""
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return " ".join(found.text.split())
    return ""


def rss_feed_result(url: str, opener=urllib.request.urlopen, limit: int = RSS_MAX_ITEMS) -> dict[str, str] | None:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 TOMOS-AI/1.0"})
    with opener(request, timeout=RSS_TIMEOUT_SECONDS) as response:
        xml_bytes = response.read()
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    feed_title = xml_text(channel, ["title"]) or xml_text(root, ["{http://www.w3.org/2005/Atom}title", "title"]) or url
    items = list(channel.findall("item")) if channel is not None else list(root.findall("{http://www.w3.org/2005/Atom}entry"))
    lines = [f"RSS/Atom: {feed_title}"]
    for item in items[: max(1, min(limit, 10))]:
        title = xml_text(item, ["title", "{http://www.w3.org/2005/Atom}title"]) or "無題"
        link = xml_text(item, ["link"])
        if not link:
            link_element = item.find("{http://www.w3.org/2005/Atom}link")
            link = str(link_element.attrib.get("href", "")) if link_element is not None else ""
        summary = xml_text(item, ["description", "summary", "{http://www.w3.org/2005/Atom}summary"])
        lines.append(f"- {title}{f' ({link})' if link else ''}{f': {summary[:180]}' if summary else ''}")
    if len(lines) == 1:
        lines.append("記事項目は見つかりませんでした。")
    return {
        "title": f"RSSフィード: {feed_title}",
        "url": url,
        "snippet": "\n".join(lines),
        "source": "agent-reach:rss",
    }


def v2ex_hot_results(opener=urllib.request.urlopen, limit: int = 5) -> list[dict[str, str]]:
    request = urllib.request.Request(
        "https://www.v2ex.com/api/topics/hot.json",
        headers={"User-Agent": "agent-reach/1.0 TOMOS-AI"},
    )
    with opener(request, timeout=COMMUNITY_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace") or "[]")
    results: list[dict[str, str]] = []
    for item in payload[: max(1, min(limit, 10))] if isinstance(payload, list) else []:
        title = str(item.get("title") or "V2EX")
        url = str(item.get("url") or "")
        node = item.get("node") or {}
        member = item.get("member") or {}
        results.append({
            "title": f"V2EX: {title}",
            "url": url,
            "snippet": "\n".join(part for part in [
                f"タイトル: {title}",
                f"ノード: {node.get('title')}" if isinstance(node, dict) and node.get("title") else "",
                f"投稿者: {member.get('username')}" if isinstance(member, dict) and member.get("username") else "",
                f"返信数: {item.get('replies')}" if item.get("replies") is not None else "",
            ] if part),
            "source": "agent-reach:v2ex",
        })
    return [item for item in results if item["url"]]


def bilibili_search_results(query: str, opener=urllib.request.urlopen, limit: int = 5) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({"keyword": query, "page": 1})
    request = urllib.request.Request(
        f"https://api.bilibili.com/x/web-interface/search/all/v2?{params}",
        headers={
            "User-Agent": "Mozilla/5.0 TOMOS-AI/1.0",
            "Referer": "https://www.bilibili.com/",
        },
    )
    with opener(request, timeout=COMMUNITY_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
    groups = payload.get("data", {}).get("result", []) if isinstance(payload, dict) else []
    videos: list[dict[str, object]] = []
    for group in groups if isinstance(groups, list) else []:
        if group.get("result_type") == "video" and isinstance(group.get("data"), list):
            videos.extend(group["data"])
    results: list[dict[str, str]] = []
    for item in videos[: max(1, min(limit, 10))]:
        title = re.sub(r"<[^>]+>", "", str(item.get("title") or "Bilibili"))
        bvid = str(item.get("bvid") or "")
        url = f"https://www.bilibili.com/video/{bvid}" if bvid else str(item.get("arcurl") or "")
        author = str(item.get("author") or "")
        description = str(item.get("description") or "")
        results.append({
            "title": f"Bilibili: {title}",
            "url": url,
            "snippet": "\n".join(part for part in [
                f"タイトル: {title}",
                f"投稿者: {author}" if author else "",
                f"説明: {description[:220]}" if description else "",
            ] if part),
            "source": "agent-reach:bilibili",
        })
    return [item for item in results if item["url"]]


def youtube_transcript_result(url: str, runner=subprocess.run) -> dict[str, str] | None:
    command_base = agent_reach_venv_ytdlp_command()
    if not command_base:
        return None
    metadata_result = runner(
        [*command_base, *YOUTUBE_YTDLP_CLIENT_ARGS, "--dump-json", "--skip-download", "--no-warnings", url],
        check=False,
        capture_output=True,
        timeout=YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS,
    )
    if getattr(metadata_result, "returncode", 1) != 0:
        raise RuntimeError(decode_subprocess_output(getattr(metadata_result, "stderr", "")) or "YouTube情報を取得できませんでした。")
    metadata_text = decode_subprocess_output(getattr(metadata_result, "stdout", ""))
    metadata = json.loads(metadata_text.splitlines()[0]) if metadata_text.strip() else {}
    video_id = str(metadata.get("id") or "")
    title = str(metadata.get("title") or "YouTube")
    description = " ".join(str(metadata.get("description") or "").split())[:1200]
    transcript = youtube_transcript_from_metadata(metadata)
    with tempfile.TemporaryDirectory(prefix="tomos-youtube-") as tmp:
        output_template = str(Path(tmp) / "%(id)s.%(ext)s")
        if not transcript:
            runner(
                [
                    *command_base,
                    *YOUTUBE_YTDLP_CLIENT_ARGS,
                    "--write-sub",
                    "--write-auto-sub",
                    "--sub-lang",
                    "ja,en,zh-Hans,zh-Hant,zh.*",
                    "--sub-format",
                    "vtt",
                    "--skip-download",
                    "--no-warnings",
                    "-o",
                    output_template,
                    url,
                ],
                check=False,
                capture_output=True,
                timeout=YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS,
            )
            subtitle_files = sorted(Path(tmp).glob("*.vtt"))
            preferred = [path for path in subtitle_files if ".ja." in path.name] or subtitle_files
            for path in preferred[:2]:
                transcript = clean_youtube_vtt_text(path.read_text(encoding="utf-8", errors="replace"))
                if transcript:
                    break
    snippet_parts = [f"動画タイトル: {title}"]
    if transcript:
        snippet_parts.append(f"字幕抜粋:\n{transcript}")
    elif description:
        snippet_parts.append(f"説明欄抜粋:\n{description}")
    else:
        snippet_parts.append("字幕または説明欄の本文を取得できませんでした。")
    return {
        "title": f"YouTube動画: {title}",
        "url": url,
        "snippet": "\n\n".join(snippet_parts),
        "source": "agent-reach:youtube",
        "videoId": video_id,
    }


ROUTE_FAILURE_REASONS = {
    "web": "Web本文を取得できませんでした。",
    "youtube": "YouTube字幕を取得できませんでした。",
    "github": "GitHub情報を取得できませんでした。",
    "rss": "RSSフィードを取得できませんでした。",
}


class RoutedWebSearchError(RuntimeError):
    def __init__(self, diagnostic: dict[str, object]) -> None:
        self.diagnostic = diagnostic
        super().__init__(str(diagnostic.get("message") or "Web検索結果を取得できませんでした。"))


class RoutedReaderError(RuntimeError):
    def __init__(self, channel: str) -> None:
        self.reason = ROUTE_FAILURE_REASONS[channel]
        super().__init__(self.reason)


def _route_diagnostic(
    decision: RouteDecision,
    fallback: bool = False,
    error_code: str = "",
    reason: str = "",
) -> dict[str, object]:
    return route_diagnostic(
        decision.channel,
        decision.backend,
        fallback=fallback,
        route_reason=reason or decision.reason,
        error_code=error_code,
    )


def routed_web_search(query: str, limit: int, exa_search, tomos_search) -> tuple[list[dict[str, str]], dict[str, object]]:
    try:
        results = exa_search(query, limit)
        return copy_web_search_results_with_route(
            results, "exa", "doctorで利用可能と確認"
        ), route_diagnostic("web", "exa")
    except Exception:
        try:
            results = tomos_search(query, limit)
        except Exception as exc:
            diagnostic = route_diagnostic("web", "exa", fallback=True, error_code="fallback-failed")
            raise RoutedWebSearchError(diagnostic) from exc
        diagnostic = route_diagnostic("web", "exa", fallback=True, error_code="priority-failed")
        return copy_web_search_results_with_route(
            results, "tomos", str(diagnostic["message"])
        ), diagnostic


def copy_web_search_results_with_route(
    results: list[dict[str, str]], backend: str, route_reason: str
) -> list[dict[str, str]]:
    return [
        {
            **result,
            "backend": backend,
            "routeReason": route_reason,
        }
        for result in results
    ]


def web_search_results_for_decision(
    decision: RouteDecision,
    query: str,
    limit: int,
    exa_search,
    tomos_search,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    if decision.backend == "exa":
        return routed_web_search(query, limit, exa_search, tomos_search)
    results = tomos_search(query, limit)
    return copy_web_search_results_with_route(
        results, decision.backend, decision.reason
    ), _route_diagnostic(decision)


def internet_layer_context_results(
    query: str,
    channels: list[str],
    runner=subprocess.run,
    diagnostics_out: list[dict[str, object]] | None = None,
    doctor_cache=None,
    route_selector=select_route,
    web_reader=None,
    youtube_reader=None,
    github_reader=None,
    rss_reader=None,
) -> tuple[list[dict[str, str]], str]:
    results: list[dict[str, str]] = []
    errors: list[str] = []
    web_reader = web_reader or web_reader_result
    youtube_reader = youtube_reader or youtube_transcript_result
    github_reader = github_reader or github_repo_result
    rss_reader = rss_reader or rss_feed_result

    def routed_result(channel: str, reader, *args, **kwargs):
        decision = agent_reach_route_decision(
            channel,
            doctor_cache=doctor_cache,
            route_selector=route_selector,
        )
        try:
            result = reader(*args, **kwargs)
        except Exception:
            if diagnostics_out is not None:
                diagnostics_out.append(_route_diagnostic(
                    decision,
                    error_code="route-failed",
                    reason=ROUTE_FAILURE_REASONS[channel],
                ))
            raise RoutedReaderError(channel) from None
        if isinstance(result, dict):
            result = {
                **result,
                "backend": decision.backend,
                "routeReason": decision.reason,
            }
        if diagnostics_out is not None:
            diagnostics_out.append(_route_diagnostic(decision))
        return result

    if "youtube" in channels:
        for url in extract_youtube_urls(query):
            try:
                result = routed_result("youtube", youtube_reader, url, runner=runner)
                if result:
                    results.append(result)
            except RoutedReaderError as exc:
                errors.append(exc.reason)
            except Exception as exc:
                errors.append(f"YouTube字幕取得: {exc}")
    if "web" in channels:
        for url in extract_web_urls(query):
            try:
                result = routed_result("web", web_reader, url)
                if result:
                    results.append(result)
            except RoutedReaderError as exc:
                errors.append(exc.reason)
            except Exception as exc:
                errors.append(f"Web本文取得: {exc}")
    if "github" in channels:
        repos = extract_github_repos(query)
        for repo in repos:
            try:
                result = routed_result("github", github_reader, repo, runner=runner)
                if result:
                    results.append(result)
            except RoutedReaderError as exc:
                errors.append(exc.reason)
            except Exception as exc:
                errors.append(f"GitHub取得: {exc}")
        if not repos and re.search(r"\bgithub\b|リポジトリ|repository|repo", query, re.IGNORECASE):
            try:
                results.extend(github_search_results(query, runner=runner, limit=3))
            except Exception as exc:
                errors.append(f"GitHub検索: {exc}")
    if "rss" in channels and re.search(r"\brss\b|atom|フィード|feed", query, re.IGNORECASE):
        for url in extract_web_urls(query):
            try:
                result = routed_result("rss", rss_reader, url)
                if result:
                    results.append(result)
            except RoutedReaderError as exc:
                errors.append(exc.reason)
            except Exception as exc:
                errors.append(f"RSS取得: {exc}")
    if "v2ex" in channels and re.search(r"\bv2ex\b", query, re.IGNORECASE):
        try:
            results.extend(v2ex_hot_results(limit=5))
        except Exception as exc:
            errors.append(f"V2EX取得: {exc}")
    if "bilibili" in channels and re.search(r"\bbilibili\b|B站|ビリビリ", query, re.IGNORECASE):
        try:
            results.extend(bilibili_search_results(query, limit=5))
        except Exception as exc:
            errors.append(f"Bilibili検索: {exc}")
    return results, " / ".join(errors)


def internet_layer_diagnostics_payload() -> dict[str, object]:
    executable = agent_reach_executable()
    detected = bool(executable)
    base_status = "ready" if detected else "missing"
    channels = {
        "web": {"status": base_status, "requiresPermission": False},
        "github": {"status": base_status, "requiresPermission": False},
        "youtube": {"status": base_status, "requiresPermission": False},
        "rss": {"status": base_status, "requiresPermission": False},
        "v2ex": {"status": base_status, "requiresPermission": False},
        "bilibili": {"status": base_status, "requiresPermission": False},
        "sns": {"status": "permission-required", "requiresPermission": True},
    }
    return {
        "ok": True,
        "tool": "Agent-Reach",
        "installed": detected,
        "executable": executable,
        "status": "ready" if detected else "not-installed",
        "contract": agent_reach_command_contract(executable),
        "channels": channels,
        "memoryAutoSave": False,
    }


def parse_agent_reach_doctor_output(text: str) -> dict[str, object]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    candidates = [raw]
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if lines:
        candidates.append(lines[-1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    marker_map = {
        "web": ["任意网页", "任意網頁", "web page", "web pages"],
        "github": ["github"],
        "youtube": ["youtube"],
        "rss": ["rss/atom", "rss"],
    }
    lower_raw = raw.lower()
    parsed: dict[str, object] = {}
    for channel, markers in marker_map.items():
        if any(marker.lower() in lower_raw for marker in markers):
            parsed[channel] = True
    if parsed:
        parsed["ok"] = True
    return parsed
    return {}


def normalize_agent_reach_channel_status(value: object) -> str:
    if isinstance(value, bool):
        return "ready" if value else "missing"
    if isinstance(value, dict):
        if value.get("ok") is True or value.get("available") is True or value.get("ready") is True:
            return "ready"
        if value.get("ok") is False or value.get("available") is False or value.get("ready") is False:
            return "missing"
        value = value.get("status", "")
    normalized = str(value or "").strip().lower()
    if normalized in {"ok", "ready", "available", "enabled", "pass", "passed", "true"}:
        return "ready"
    if normalized in {"missing", "not-installed", "unavailable", "disabled", "fail", "failed", "false"}:
        return "missing"
    return "checking"


def agent_reach_doctor_channels(doctor: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_channels = doctor.get("channels") if isinstance(doctor.get("channels"), dict) else {}
    channels: dict[str, dict[str, object]] = {}
    for channel in ["web", "github", "youtube", "rss", "v2ex", "bilibili", "sns"]:
        raw_value = raw_channels.get(channel) if isinstance(raw_channels, dict) and channel in raw_channels else doctor.get(channel)
        if raw_value is None:
            raw_value = "permission-required" if channel == "sns" else "checking"
        status = "permission-required" if channel == "sns" and raw_value in {None, ""} else normalize_agent_reach_channel_status(raw_value)
        if channel == "sns" and status == "checking":
            status = "permission-required"
        channels[channel] = {
            "status": status,
            "requiresPermission": channel == "sns",
        }
    return channels


def normalize_internet_layer_channels(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed = {"web", "github", "youtube", "rss", "v2ex", "bilibili", "sns"}
    channels: list[str] = []
    for item in value:
        channel = str(item or "").strip().lower()
        if channel in allowed and channel not in channels:
            channels.append(channel)
    return channels


def agent_reach_doctor_payload(runner=subprocess.run) -> dict[str, object]:
    diagnostics = internet_layer_diagnostics_payload()
    executable = str(diagnostics.get("executable") or "")
    if not executable:
        return {
            "ok": True,
            "installed": False,
            "status": "not-installed",
            "message": "エージェントリーチは未導入です。",
            "contract": diagnostics.get("contract") or agent_reach_command_contract(),
            "doctor": {},
        }
    command = [executable, "doctor", "--json"]
    try:
        result = runner(
            command,
            check=False,
            capture_output=True,
            timeout=AGENT_REACH_DOCTOR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "installed": True,
            "status": "timeout",
            "message": "エージェントリーチ診断が時間内に完了しませんでした。",
            "command": command,
            "contract": diagnostics.get("contract") or agent_reach_command_contract(executable),
            "doctor": {},
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "ok": False,
            "installed": True,
            "status": "error",
            "message": str(exc),
            "command": command,
            "contract": diagnostics.get("contract") or agent_reach_command_contract(executable),
            "doctor": {},
        }
    stdout = decode_subprocess_output(getattr(result, "stdout", ""))
    stderr = decode_subprocess_output(getattr(result, "stderr", ""))
    doctor = parse_agent_reach_doctor_output(stdout)
    channels = agent_reach_doctor_channels(doctor)
    return {
        "ok": getattr(result, "returncode", 1) == 0,
        "installed": True,
        "status": "ready" if getattr(result, "returncode", 1) == 0 else "error",
        "message": "エージェントリーチ診断が完了しました。" if getattr(result, "returncode", 1) == 0 else "エージェントリーチ診断でエラーが出ました。",
        "command": command,
        "contract": diagnostics.get("contract") or agent_reach_command_contract(executable),
        "doctor": doctor,
        "channels": channels,
        "stdout": stdout[-4000:],
        "stderr": stderr[-2000:],
    }


def agent_reach_doctor_snapshot() -> dict[str, object]:
    payload = agent_reach_doctor_payload()
    doctor = payload.get("doctor")
    if not payload.get("ok") or not payload.get("installed") or not isinstance(doctor, dict):
        return {"installed": False}
    return {**doctor, "installed": True}


AGENT_REACH_DOCTOR_CACHE = DoctorCache(agent_reach_doctor_snapshot)


def agent_reach_route_decision(
    channel: str,
    intent: str = "read",
    doctor_cache=None,
    route_selector=select_route,
) -> RouteDecision:
    cache = doctor_cache or AGENT_REACH_DOCTOR_CACHE
    try:
        doctor = cache.get()
        if not isinstance(doctor, dict):
            raise ValueError("診断結果が不正です")
        return route_selector(channel, doctor, intent=intent)
    except Exception:
        return RouteDecision(
            channel=channel,
            backend="tomos",
            fallback="",
            reason="doctorで利用不可のため現行TOMOS経路を使用",
        )


def internet_layer_setup_status() -> dict[str, object]:
    with INTERNET_LAYER_SETUP_LOCK:
        job = dict(INTERNET_LAYER_SETUP_JOB)
    return {"ok": True, "job": job, "internetLayer": internet_layer_diagnostics_payload()}


def update_internet_layer_setup_job(**updates: object) -> None:
    with INTERNET_LAYER_SETUP_LOCK:
        job = dict(INTERNET_LAYER_SETUP_JOB)
        logs = list(job.get("logs") or [])
        message = str(updates.get("message") or "")
        if message:
            logs.append(message)
        job.update(updates)
        job["logs"] = logs[-8:]
        INTERNET_LAYER_SETUP_JOB.clear()
        INTERNET_LAYER_SETUP_JOB.update(job)


def run_internet_layer_setup_command(command: list[str], message: str, step: int, total: int) -> None:
    update_internet_layer_setup_job(message=message, step=step, total=total, percent=min(99, round(step / max(total, 1) * 100)))
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    last_line = ""
    for line in iter_subprocess_output_lines(process):
        last_line = line or last_line
        if last_line:
            update_internet_layer_setup_job(message=last_line)
    code = process.wait()
    if code != 0:
        raise RuntimeError(last_line or f"コマンドが終了コード {code} で失敗しました。")


def run_internet_layer_setup() -> None:
    total = 4
    try:
        update_internet_layer_setup_job(
            status="running",
            message="エージェントリーチ安全導入を開始しました。",
            step=0,
            total=total,
            percent=0,
            startedAt=time.time(),
            finishedAt=None,
        )
        venv_python = agent_reach_venv_python()
        if not venv_python.exists():
            run_internet_layer_setup_command(
                [sys.executable, "-m", "venv", str(AGENT_REACH_VENV_DIR)],
                "専用環境を作成しています。",
                1,
                total,
            )
        else:
            update_internet_layer_setup_job(message="専用環境は作成済みです。", step=1, total=total, percent=25)
        run_internet_layer_setup_command(
            [str(venv_python), "-m", "pip", "install", "--upgrade", AGENT_REACH_PACKAGE_URL],
            "エージェントリーチを導入しています。",
            2,
            total,
        )
        executable = str(agent_reach_venv_executable())
        run_internet_layer_setup_command(
            [executable, "install", "--env=auto", "--safe"],
            "安全モードの初期設定を実行しています。",
            3,
            total,
        )
        doctor = agent_reach_doctor_payload()
        final_message = "エージェントリーチ安全導入が完了しました。" if doctor.get("ok") or doctor.get("installed") else "導入後の診断で確認が必要です。"
        update_internet_layer_setup_job(
            status="done",
            message=final_message,
            step=total,
            total=total,
            percent=100,
            doctor=doctor,
            finishedAt=time.time(),
        )
    except Exception as exc:
        update_internet_layer_setup_job(status="error", message=str(exc), finishedAt=time.time())


def start_internet_layer_setup() -> dict[str, object]:
    with INTERNET_LAYER_SETUP_LOCK:
        if INTERNET_LAYER_SETUP_JOB.get("status") == "running":
            return {"ok": True, "status": "running", "message": str(INTERNET_LAYER_SETUP_JOB.get("message", ""))}
        INTERNET_LAYER_SETUP_JOB.clear()
        INTERNET_LAYER_SETUP_JOB.update({
            "status": "queued",
            "message": "エージェントリーチ安全導入待機中です。",
            "step": 0,
            "total": 4,
            "percent": 0,
            "logs": ["エージェントリーチ安全導入待機中です。"],
            "startedAt": time.time(),
            "finishedAt": None,
        })
    thread = threading.Thread(target=run_internet_layer_setup, daemon=True)
    thread.start()
    return {"ok": True, "status": "running", "message": "エージェントリーチ安全導入を開始しました。"}


def health_payload() -> dict:
    try:
        version = ollama_json("/api/version", timeout=3).get("version", "unknown")
        models = installed_ollama_models()
        installed = MODEL in models
        coding_model = select_coding_model()
        translation_model = select_translation_model()
        return {
            "ok": True,
            "ollama": "running",
            "version": version,
            "appVersion": APP_VERSION,
            "appCommit": app_commit(),
            "model": MODEL,
            "codingModel": coding_model,
            "translationModel": translation_model,
            "models": {
                "chat": MODEL,
                "coding": coding_model,
                "translation": translation_model,
            },
            "availableModels": sorted(models),
            "recommendedCodingModels": list(dict.fromkeys(
                model for model in [CODING_MODEL, *CODING_MODEL_CANDIDATES]
                if model
            )),
            "pullableModels": PULLABLE_MODELS,
            "pcDiagnostics": pc_diagnostics_payload(
                available_models=models,
                ollama_version=str(version),
            ),
            "internetLayer": internet_layer_diagnostics_payload(),
            "searchCapabilities": workspace_search_capabilities(),
            "modelInstalled": installed,
            "codingModelInstalled": coding_model in models,
            "translationModelInstalled": translation_model in models,
        }
    except Exception as exc:
        return {
            "ok": False,
            "ollama": "offline",
            "appVersion": APP_VERSION,
            "appCommit": app_commit(),
            "model": MODEL,
            "codingModel": select_coding_model(),
            "translationModel": TRANSLATION_MODEL or MODEL,
            "models": {
                "chat": MODEL,
                "coding": select_coding_model(),
                "translation": TRANSLATION_MODEL or MODEL,
            },
            "availableModels": [],
            "recommendedCodingModels": list(dict.fromkeys(
                model for model in [CODING_MODEL, *CODING_MODEL_CANDIDATES]
                if model
            )),
            "pullableModels": PULLABLE_MODELS,
            "pcDiagnostics": pc_diagnostics_payload(
                available_models=set(),
                ollama_version="",
            ),
            "internetLayer": internet_layer_diagnostics_payload(),
            "searchCapabilities": workspace_search_capabilities(),
            "modelInstalled": False,
            "codingModelInstalled": False,
            "translationModelInstalled": False,
            "error": str(exc),
        }


def reconcile_model_pull_jobs() -> set[str] | None:
    try:
        models = installed_ollama_models(force_refresh=True)
    except Exception:
        return None
    now = time.time()
    with MODEL_PULL_LOCK:
        for model, job in list(MODEL_PULL_JOBS.items()):
            if model in models and job.get("status") in {"queued", "running"}:
                job.update({
                    "status": "done",
                    "message": "ダウンロードが完了しました。",
                    "finishedAt": job.get("finishedAt") or now,
                })
                MODEL_PULL_JOBS[model] = job
    return models


def model_pull_status() -> dict:
    models = reconcile_model_pull_jobs()
    with MODEL_PULL_LOCK:
        jobs = {model: dict(job) for model, job in MODEL_PULL_JOBS.items()}
    response = {"ok": True, "jobs": jobs}
    if models is not None:
        response["availableModels"] = sorted(models)
    return response


def run_model_pull(model: str) -> None:
    with MODEL_PULL_LOCK:
        MODEL_PULL_JOBS[model] = {
            "model": model,
            "status": "running",
            "message": "ダウンロードを開始しました。",
            "startedAt": time.time(),
            "finishedAt": None,
        }
    try:
        process = subprocess.Popen(
            ["ollama", "pull", model],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        last_line = ""
        for line in iter_subprocess_output_lines(process):
            last_line = line or last_line
            if last_line:
                with MODEL_PULL_LOCK:
                    job = MODEL_PULL_JOBS.get(model, {})
                    job.update({"message": last_line})
                    MODEL_PULL_JOBS[model] = job
        code = process.wait()
        if code == 0:
            try:
                installed_ollama_models(force_refresh=True)
            except Exception:
                pass
        with MODEL_PULL_LOCK:
            job = MODEL_PULL_JOBS.get(model, {})
            job.update({
                "status": "done" if code == 0 else "error",
                "message": "ダウンロードが完了しました。" if code == 0 else last_line or f"ollama pull が終了コード {code} で失敗しました。",
                "finishedAt": time.time(),
            })
            MODEL_PULL_JOBS[model] = job
    except Exception as exc:
        with MODEL_PULL_LOCK:
            job = MODEL_PULL_JOBS.get(model, {})
            job.update({"status": "error", "message": str(exc), "finishedAt": time.time()})
            MODEL_PULL_JOBS[model] = job


def start_model_pull(model: str) -> dict:
    if model not in PULLABLE_MODEL_NAMES:
        raise ValueError("このモデルはUIからダウンロードできません。")
    try:
        already_installed = model in installed_ollama_models()
    except Exception:
        already_installed = False
    if already_installed:
        with MODEL_PULL_LOCK:
            MODEL_PULL_JOBS[model] = {
                "model": model,
                "status": "done",
                "message": "すでにダウンロード済みです。",
                "startedAt": time.time(),
                "finishedAt": time.time(),
            }
        return {"ok": True, "model": model, "status": "done", "message": "すでにダウンロード済みです。"}
    with MODEL_PULL_LOCK:
        existing = MODEL_PULL_JOBS.get(model)
        if existing and existing.get("status") == "running":
            return {"ok": True, "model": model, "status": "running", "message": str(existing.get("message", ""))}
        MODEL_PULL_JOBS[model] = {
            "model": model,
            "status": "queued",
            "message": "ダウンロード待機中です。",
            "startedAt": time.time(),
            "finishedAt": None,
        }
    thread = threading.Thread(target=run_model_pull, args=(model,), daemon=True)
    thread.start()
    return {"ok": True, "model": model, "status": "running", "message": "ダウンロードを開始しました。"}


def validate_model_remove(model: str) -> str:
    normalized = str(model or "").strip()
    if normalized not in PULLABLE_MODEL_NAMES:
        raise ValueError("このモデルはUIからアンインストールできません。")
    return normalized


def remove_model(model: str) -> dict:
    normalized = validate_model_remove(model)
    process = subprocess.run(
        ["ollama", "rm", normalized],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )
    if process.returncode != 0:
        message = (process.stdout or "").strip() or f"ollama rm が終了コード {process.returncode} で失敗しました。"
        raise RuntimeError(message)
    models = installed_ollama_models(force_refresh=True)
    return {
        "ok": True,
        "model": normalized,
        "message": "モデルをアンインストールしました。",
        "availableModels": sorted(models),
    }


def asr_setup_status() -> dict:
    with ASR_SETUP_LOCK:
        job = dict(ASR_SETUP_JOB)
    return {"ok": True, "job": job}


def run_asr_setup() -> None:
    script = ROOT / "scripts" / "setup-asr-nemotron-mac.sh"
    with ASR_SETUP_LOCK:
        ASR_SETUP_JOB.update({
            "status": "running",
            "message": "ASRセットアップを開始しました。",
            "startedAt": time.time(),
            "finishedAt": None,
        })
    try:
        process = subprocess.Popen(
            ["bash", str(script)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        last_line = ""
        for line in iter_subprocess_output_lines(process):
            last_line = line or last_line
            if last_line:
                with ASR_SETUP_LOCK:
                    ASR_SETUP_JOB.update({"message": last_line})
        code = process.wait()
        with ASR_SETUP_LOCK:
            ASR_SETUP_JOB.update({
                "status": "done" if code == 0 else "error",
                "message": "ASRセットアップが完了しました。" if code == 0 else last_line or f"ASRセットアップが終了コード {code} で失敗しました。",
                "finishedAt": time.time(),
            })
    except Exception as exc:
        with ASR_SETUP_LOCK:
            ASR_SETUP_JOB.update({"status": "error", "message": str(exc), "finishedAt": time.time()})


def start_asr_setup() -> dict:
    if sys.platform != "darwin":
        raise RuntimeError("ASRセットアップの自動実行は現在Mac用です。Windowsでは docs/asr-nemotron-setup.ja.md の手順を使ってください。")
    script = ROOT / "scripts" / "setup-asr-nemotron-mac.sh"
    if not script.exists():
        raise RuntimeError("ASRセットアップスクリプトが見つかりません。")
    with ASR_SETUP_LOCK:
        existing = ASR_SETUP_JOB.get("status")
        if existing == "running":
            return {"ok": True, "status": "running", "message": str(ASR_SETUP_JOB.get("message", ""))}
        ASR_SETUP_JOB.clear()
        ASR_SETUP_JOB.update({
            "status": "queued",
            "message": "ASRセットアップ待機中です。",
            "startedAt": time.time(),
            "finishedAt": None,
        })
    thread = threading.Thread(target=run_asr_setup, daemon=True)
    thread.start()
    return {"ok": True, "status": "running", "message": "ASRセットアップを開始しました。"}


def ocr_setup_status() -> dict:
    with OCR_SETUP_LOCK:
        job = dict(OCR_SETUP_JOB)
    return {"ok": True, "job": job, "ocr": ocr_capabilities()}


def run_ocr_setup() -> None:
    script = ROOT / "scripts" / "setup-ocr-mac.sh"
    with OCR_SETUP_LOCK:
        OCR_SETUP_JOB.update({
            "status": "running",
            "message": "OCRセットアップを開始しました。",
            "step": 0,
            "total": 5,
            "percent": 0,
            "logs": ["OCRセットアップを開始しました。"],
            "startedAt": time.time(),
            "finishedAt": None,
        })
    try:
        process = subprocess.Popen(
            ["bash", str(script)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        last_line = ""
        for line in iter_subprocess_output_lines(process):
            last_line = line or last_line
            if last_line:
                progress_match = re.match(r"^PROGRESS\s+(\d+)/(\d+)\s+(.+)$", last_line)
                with OCR_SETUP_LOCK:
                    logs = list(OCR_SETUP_JOB.get("logs") or [])
                    if progress_match:
                        step = int(progress_match.group(1))
                        total = max(int(progress_match.group(2)), 1)
                        message = progress_match.group(3)
                        logs.append(message)
                        OCR_SETUP_JOB.update({
                            "message": message,
                            "step": step,
                            "total": total,
                            "percent": min(99, round(step / total * 100)),
                            "logs": logs[-8:],
                        })
                    else:
                        logs.append(last_line)
                        OCR_SETUP_JOB.update({"message": last_line, "logs": logs[-8:]})
        code = process.wait()
        with OCR_SETUP_LOCK:
            logs = list(OCR_SETUP_JOB.get("logs") or [])
            final_message = "OCRセットアップが完了しました。" if code == 0 else last_line or f"OCRセットアップが終了コード {code} で失敗しました。"
            logs.append(final_message)
            OCR_SETUP_JOB.update({
                "status": "done" if code == 0 else "error",
                "message": final_message,
                "percent": 100 if code == 0 else int(OCR_SETUP_JOB.get("percent") or 0),
                "logs": logs[-8:],
                "finishedAt": time.time(),
            })
    except Exception as exc:
        with OCR_SETUP_LOCK:
            logs = list(OCR_SETUP_JOB.get("logs") or [])
            logs.append(str(exc))
            OCR_SETUP_JOB.update({"status": "error", "message": str(exc), "logs": logs[-8:], "finishedAt": time.time()})


def start_ocr_setup() -> dict:
    if sys.platform != "darwin":
        raise RuntimeError("OCRセットアップの自動実行は現在Mac用です。WindowsではTesseractとPopplerを手動で導入してください。")
    script = ROOT / "scripts" / "setup-ocr-mac.sh"
    if not script.exists():
        raise RuntimeError("OCRセットアップスクリプトが見つかりません。")
    with OCR_SETUP_LOCK:
        existing = OCR_SETUP_JOB.get("status")
        if existing == "running":
            return {"ok": True, "status": "running", "message": str(OCR_SETUP_JOB.get("message", ""))}
        OCR_SETUP_JOB.clear()
        OCR_SETUP_JOB.update({
            "status": "queued",
            "message": "OCRセットアップ待機中です。",
            "step": 0,
            "total": 5,
            "percent": 0,
            "logs": ["OCRセットアップ待機中です。"],
            "startedAt": time.time(),
            "finishedAt": None,
        })
    thread = threading.Thread(target=run_ocr_setup, daemon=True)
    thread.start()
    return {"ok": True, "status": "running", "message": "OCRセットアップを開始しました。"}


class Handler(BaseHTTPRequestHandler):
    server_version = "GemmaWebUI/1.0"
    static_only = False
    mobile_sync_only = False

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/mobile/") and not mobile_api_access_allowed(
            "GET",
            parsed.path,
            str(self.client_address[0]),
        ):
            json_response(self, 403, {"ok": False, "error": "mobile api is restricted to this PC"})
            return
        if (self.static_only or self.mobile_sync_only) and not static_preview_get_api_allowed(
            parsed.path,
            allow_mobile_sync=self.mobile_sync_only,
        ):
            json_response(self, 403, {"ok": False, "error": "mobile static preview blocks API reads"})
            return
        if parsed.path == "/api/health":
            payload = health_payload()
            if self.static_only:
                payload = {
                    **payload,
                    "ok": True,
                    "mobilePreview": True,
                    "modelInstalled": False,
                    "codingModelInstalled": False,
                    "translationModelInstalled": False,
                }
            json_response(self, 200 if payload["ok"] else 503, payload)
            return
        if parsed.path == "/api/mobile/connect-info":
            host, port = self.server.server_address[:2]
            public_port = None
            if is_loopback_client(str(host)):
                sync_port = configured_mobile_sync_port()
                if sync_port != int(port):
                    sync_payload = local_mobile_sync_connect_info(sync_port)
                    if sync_payload:
                        json_response(self, 200, sync_payload)
                        return
                public_port = sync_port
            json_response(self, 200, mobile_connect_info(str(host), int(port), public_port=public_port))
            return
        if parsed.path == "/api/mobile/qr.svg":
            query = urllib.parse.parse_qs(parsed.query)
            text = query.get("text", [""])[0]
            if not text:
                self.send_error(400)
                return
            try:
                svg_response(self, 200, mobile_qr_svg(text))
            except ValueError:
                self.send_error(400)
            except RuntimeError as exc:
                json_response(self, 503, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/api/mobile/imports":
            json_response(self, 200, {"ok": True, "imports": mobile_pending_imports()})
            return
        if parsed.path == "/api/asr/status":
            json_response(self, 200, asr_status_payload())
            return
        if parsed.path == "/api/asr/setup/status":
            json_response(self, 200, asr_setup_status())
            return
        if parsed.path == "/api/ocr/setup/status":
            json_response(self, 200, ocr_setup_status())
            return
        if parsed.path == "/api/internet-layer/status":
            json_response(self, 200, internet_layer_diagnostics_payload())
            return
        if parsed.path == "/api/internet-layer/contract":
            json_response(self, 200, {"ok": True, "contract": agent_reach_command_contract()})
            return
        if parsed.path == "/api/internet-layer/doctor":
            payload = agent_reach_doctor_payload()
            json_response(self, 200 if payload.get("ok") or payload.get("status") == "not-installed" else 503, payload)
            return
        if parsed.path == "/api/internet-layer/setup/status":
            json_response(self, 200, internet_layer_setup_status())
            return
        if parsed.path == "/api/contracts/pdf-import/status":
            json_response(self, 200, contract_pdf_import_status_payload())
            return
        if parsed.path == "/api/contracts/pdf-import/test":
            json_response(self, 200, contract_pdf_import_connection_test_payload())
            return
        if parsed.path == "/api/contracts/pdf-import/sarashina/status":
            json_response(self, 200, sarashina_ocr_status())
            return
        if parsed.path == "/api/models/pull/status":
            json_response(self, 200, model_pull_status())
            return
        if parsed.path == "/api/image/status":
            payload = comfyui_status_payload()
            json_response(self, 200 if payload["ok"] else 503, payload)
            return
        if parsed.path == "/api/image/view":
            self.handle_image_view(parsed.query)
            return
        if parsed.path == "/api/person-photo/view":
            self.handle_person_photo_view(parsed.query)
            return
        if parsed.path == "/api/workspace/preview":
            self.handle_workspace_preview(parsed.query)
            return
        if parsed.path == "/api/knowledge/status":
            self.handle_knowledge_status(parsed.query)
            return
        if parsed.path == "/api/context/memory/list":
            query = urllib.parse.parse_qs(parsed.query)
            json_response(self, 200, context_memory_list_payload({
                "scopeType": (query.get("scopeType") or [""])[0],
                "scopeId": (query.get("scopeId") or [""])[0],
                "includeInactive": (query.get("includeInactive") or [""])[0],
            }))
            return
        if parsed.path == "/api/context/memory/profile":
            query = urllib.parse.parse_qs(parsed.query)
            json_response(self, 200, context_memory_profile_payload({
                "scopeType": (query.get("scopeType") or [""])[0],
                "scopeId": (query.get("scopeId") or [""])[0],
            }))
            return
        if parsed.path == "/api/contracts/list":
            self.handle_contracts_list(parsed.query)
            return

        path = parsed.path
        if path == "/":
            file_path = WEB_ROOT / ("mobile.html" if self.static_only else "index.html")
        elif path == "/m":
            file_path = WEB_ROOT / "mobile.html"
        elif path == "/pc-mobile-connect":
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
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path.startswith("/api/mobile/") and not mobile_api_access_allowed(
            "POST",
            self.path,
            str(self.client_address[0]),
        ):
            json_response(self, 403, {"ok": False, "error": "mobile api is restricted to this PC"})
            return
        if self.static_only or (self.mobile_sync_only and not self.path.startswith("/api/mobile/")):
            json_response(self, 403, {"ok": False, "error": "mobile static preview blocks API writes"})
            return
        if self.path == "/api/search":
            self.handle_search()
            return
        if self.path == "/api/weather":
            self.handle_weather()
            return
        if self.path == "/api/image/generate":
            self.handle_image_generate()
            return
        if self.path == "/api/person-photo/upload":
            self.handle_person_photo_upload()
            return
        if self.path == "/api/models/pull":
            self.handle_model_pull()
            return
        if self.path == "/api/models/remove":
            self.handle_model_remove()
            return
        if self.path == "/api/llm/check":
            self.handle_llm_check()
            return
        if self.path == "/api/asr/transcribe":
            self.handle_asr_transcribe()
            return
        if self.path == "/api/asr/setup":
            self.handle_asr_setup()
            return
        if self.path == "/api/ocr/setup":
            self.handle_ocr_setup()
            return
        if self.path == "/api/internet-layer/setup":
            self.handle_internet_layer_setup()
            return
        if self.path == "/api/contracts/pdf-import/try-page":
            try:
                body = read_json_body(self)
                json_response(
                    self,
                    200,
                    contract_pdf_import_try_page_payload(
                        str(body.get("path", "")),
                        body.get("page", 1),
                        bool(body.get("allPages")),
                    ),
                )
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return
        if self.path == "/api/contracts/pdf-import/auto":
            try:
                body = read_json_body(self)
                json_response(self, 200, contract_pdf_import_auto_payload(str(body.get("path", ""))))
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return
        if self.path == "/api/contracts/pdf-import/pick-pdf":
            try:
                json_response(self, 200, pick_contract_pdf_import_file())
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return
        if self.path == "/api/contracts/pdf-import/sarashina/compare-page":
            try:
                body = read_json_body(self)
                json_response(
                    self,
                    200,
                    sarashina_compare_page_payload(str(body.get("path", "")), body.get("page", 1)),
                )
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return
        if self.path == "/api/attachment/read":
            self.handle_attachment_read()
            return
        if self.path == "/api/mobile/import-chat":
            try:
                json_response(self, 200, queue_mobile_chat_import(read_json_body(self)))
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return
        if self.path == "/api/mobile/imports/clear":
            try:
                body = read_json_body(self)
                ids = body.get("ids")
                json_response(self, 200, clear_mobile_pending_imports(ids if isinstance(ids, list) else None))
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return
        if self.path.startswith("/api/workspace/"):
            self.handle_workspace()
            return
        if self.path.startswith("/api/knowledge/"):
            self.handle_knowledge()
            return
        if self.path == "/api/context/memory/save":
            try:
                payload = context_memory_save_payload(read_json_body(self))
                json_response(self, 200 if payload.get("ok") else 400, payload)
            except Exception as exc:
                json_response(self, 500, {"ok": False, "error": str(exc)})
            return
        if self.path == "/api/context/memory/forget":
            try:
                payload = context_memory_forget_payload(read_json_body(self))
                json_response(self, 200 if payload.get("ok") else 400, payload)
            except Exception as exc:
                json_response(self, 500, {"ok": False, "error": str(exc)})
            return
        if self.path == "/api/context/memory/update":
            try:
                payload = context_memory_update_payload(read_json_body(self))
                json_response(self, 200 if payload.get("ok") else 400, payload)
            except Exception as exc:
                json_response(self, 500, {"ok": False, "error": str(exc)})
            return
        if self.path.startswith("/api/contracts/"):
            self.handle_contracts()
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
            is_translation_task = body.get("task") == "translation"
            translation_target = translation_target_from_text(str(messages[-1].get("content", ""))) if is_translation_task else ""
            history_turns = max(1, min(int(body.get("history_turns", 4)), 20))
            recent_messages = sanitize_chat_messages(messages[-1:] if is_translation_task else messages[-(history_turns * 2) :])
            if is_translation_task and recent_messages:
                recent_messages[-1]["content"] = strip_translation_instruction(str(recent_messages[-1].get("content", "")))
            search_results: list[dict[str, str]] = []
            search_error = ""
            search_diagnostics: list[dict[str, str]] = []
            query = str(body.get("search_query") or messages[-1].get("content", ""))
            auto_external_research = should_auto_use_external_research(query)
            use_web_search = (bool(body.get("web_search", False)) or auto_external_research) and not is_translation_task
            internet_layer_channels = normalize_internet_layer_channels(body.get("internet_layer_channels", [])) if use_web_search else []
            if use_web_search and auto_external_research and not internet_layer_channels:
                internet_layer_channels = auto_internet_layer_channels_for_query(query)
            if use_web_search:
                route_diagnostics: list[dict[str, object]] = []
                try:
                    internet_results, internet_error = internet_layer_context_results(
                        query,
                        internet_layer_channels,
                        diagnostics_out=route_diagnostics,
                    )
                    search_results.extend(internet_results)
                    if internet_error:
                        search_error = internet_error
                except Exception as exc:
                    search_error = str(exc)
                try:
                    max_results = max(0, int(body.get("search_results", 4)) - len(search_results))
                    if max_results > 0:
                        web_search_decision = agent_reach_route_decision("web", intent="search")
                        web_results, diagnostic = web_search_results_for_decision(
                            web_search_decision,
                            query,
                            max_results,
                            run_exa_search,
                            search_web,
                        )
                        search_results.extend(web_results)
                        route_diagnostics.append(diagnostic)
                except RoutedWebSearchError as exc:
                    route_diagnostics.append(exc.diagnostic)
                    search_error = f"{search_error} / {exc}" if search_error else str(exc)
                except Exception as exc:
                    search_error = f"{search_error} / {exc}" if search_error else str(exc)
                if search_results:
                    search_results, reader_error = augment_search_results_with_page_text(query, search_results)
                    if reader_error:
                        search_error = f"{search_error} / {reader_error}" if search_error else reader_error
            complete_list_answer = should_buffer_complete_list_stream(
                use_web_search,
                query,
                internet_layer_channels,
                search_results,
            )
            if complete_list_answer:
                recent_messages = sanitize_chat_messages(messages[-1:])
            search_diagnostics = external_research_diagnostics(query, internet_layer_channels, search_results, search_error) if use_web_search else []
            if use_web_search:
                search_diagnostics.extend(route_diagnostics)
            complete_list_evidence = build_complete_list_evidence(query, search_results) if complete_list_answer else None
            answer_search_results = public_search_results_for_answer(search_results, complete_list_evidence)
            if complete_list_evidence:
                search_diagnostics.append(complete_list_diagnostic(complete_list_evidence))

            prompt_messages = [{"role": "system", "content": system_prompt}]
            if is_translation_task and translation_target:
                prompt_messages.append({
                    "role": "system",
                    "content": (
                        f"Translate every sentence of the user's source text into {translation_target}. "
                        f"Every translated sentence must be written in {translation_target}. "
                        f"Do not leave source-language sentences untranslated. "
                        f"Do not paraphrase or rewrite it in the source language. "
                        f"Do not summarize, omit, or save anything. Return only the {translation_target} translation."
                    ),
                })
            if use_web_search:
                search_context = build_search_context_for_query(query, search_results)
                if search_error:
                    search_context += f"\n\nSearch error: {search_error}"
                prompt_messages.append({"role": "system", "content": search_context})
                answer_instruction = external_research_answer_instruction(search_results, search_error)
                if answer_instruction:
                    prompt_messages.append({"role": "system", "content": answer_instruction})
                if complete_list_answer:
                    prompt_messages.append({
                        "role": "system",
                        "content": "一覧本文は決定論的に組み立てます。導入文だけを1文で返してください。「確認したよ。」または「調べたよ。」のどちらか1つだけを返してください。",
                    })
                else:
                    list_instruction = complete_list_grounding_instruction(query, search_results, search_error)
                    if list_instruction:
                        prompt_messages.append({"role": "system", "content": list_instruction})
            if body.get("workspace") and not is_translation_task:
                try:
                    workspace_context = build_workspace_context(body.get("workspace", {}))
                    if workspace_context:
                        prompt_messages.append({"role": "system", "content": workspace_context})
                except Exception as exc:
                    prompt_messages.append({"role": "system", "content": f"Workspace context error: {exc}"})
            prompt_messages.extend(recent_messages)
            if is_translation_task or body.get("workspace") or complete_list_answer:
                direct_answer = ""
            else:
                direct_answer = direct_external_research_answer(query, search_results, search_error)
            requested_model = str(body.get("model") or "").strip()
            is_coding_task = body.get("task") == "coding" or bool(body.get("coding", False))
            if requested_model:
                selected_model = requested_model
            elif is_translation_task:
                selected_model = select_translation_model()
            elif is_coding_task:
                selected_model = select_coding_model()
            else:
                selected_model = MODEL
            try:
                llm_base_url = normalize_local_llm_base_url(str(body.get("llm_base_url") or ""))
            except ValueError as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
                return

            payload = {
                "model": selected_model,
                "stream": bool(body.get("stream", False)),
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
            if payload["stream"]:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                stream_json_event(
                    self,
                    {
                        "ok": True,
                        "type": "start",
                        "model": payload["model"],
                        "task": "translation" if is_translation_task else "coding" if is_coding_task else "chat",
                        "search": {
                            "enabled": use_web_search,
                            "results": answer_search_results,
                            "error": search_error,
                            "channels": internet_layer_channels,
                            "diagnostics": search_diagnostics,
                        },
                    },
                )
                if direct_answer:
                    stream_json_event(self, {"ok": True, "type": "chunk", "content": direct_answer})
                    stream_json_event(
                        self,
                        {
                            "ok": True,
                            "type": "done",
                            "message": {"role": "assistant", "content": direct_answer},
                            "model": payload["model"],
                            "task": "chat",
                            "done": True,
                            "search": {
                                "enabled": use_web_search,
                                "results": answer_search_results,
                                "error": search_error,
                                "channels": internet_layer_channels,
                                "diagnostics": search_diagnostics,
                            },
                        },
                    )
                    return
                content_parts: list[str] = []
                try:
                    with ollama_stream("/api/chat", payload=payload, timeout=600, base_url=llm_base_url) as stream:
                        for raw_line in stream:
                            line = raw_line.decode("utf-8", errors="replace").strip()
                            if not line:
                                continue
                            chunk_data = json.loads(line)
                            chunk = str(chunk_data.get("message", {}).get("content", ""))
                            emit_or_buffer_chat_chunk(
                                chunk,
                                complete_list_answer,
                                content_parts,
                                lambda content: stream_json_event(self, {"ok": True, "type": "chunk", "content": content}),
                            )
                            if chunk_data.get("done"):
                                break
                except urllib.error.HTTPError as exc:
                    stream_json_event(self, ollama_http_error_event(exc, model=payload["model"]))
                    return
                except Exception as exc:
                    stream_json_event(
                        self,
                        {
                            "ok": False,
                            "type": "error",
                            "error": str(exc),
                            "model": payload["model"],
                        },
                    )
                    return
                content = "".join(content_parts)
                if is_translation_task:
                    content = clean_translation_output(content)
                elif complete_list_evidence:
                    content, answer_search_results, _ = finalize_complete_list_answer(
                        system_prompt,
                        search_results,
                        complete_list_evidence,
                    )
                    stream_json_event(self, {"ok": True, "type": "chunk", "content": content})
                elif use_web_search:
                    content = remove_unverified_list_items(content, query, search_results)
                    content = organize_mixed_list_categories(content, query, search_results)
                stream_json_event(
                    self,
                    {
                        "ok": True,
                        "type": "done",
                        "message": {"role": "assistant", "content": content},
                        "model": payload["model"],
                        "task": "translation" if is_translation_task else "coding" if is_coding_task else "chat",
                        "done": True,
                        "search": {
                            "enabled": use_web_search,
                            "results": answer_search_results,
                            "error": search_error,
                            "channels": internet_layer_channels,
                            "diagnostics": search_diagnostics,
                        },
                    },
                )
                return

            payload["stream"] = False
            if direct_answer:
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "message": {"role": "assistant", "content": direct_answer},
                        "model": payload["model"],
                        "task": "chat",
                        "done": True,
                        "search": {
                            "enabled": use_web_search,
                            "results": answer_search_results,
                            "error": search_error,
                            "channels": internet_layer_channels,
                            "diagnostics": search_diagnostics,
                        },
                    },
                )
                return
            response = ollama_json("/api/chat", payload=payload, timeout=600, base_url=llm_base_url)
            message = response.get("message", {})
            if is_translation_task and isinstance(message, dict):
                message = {**message, "content": clean_translation_output(str(message.get("content", "")))}
            elif complete_list_evidence and isinstance(message, dict):
                content, answer_search_results, _ = finalize_complete_list_answer(
                    system_prompt,
                    search_results,
                    complete_list_evidence,
                )
                message = {**message, "content": content}
            elif use_web_search and isinstance(message, dict):
                web_content = remove_unverified_list_items(str(message.get("content", "")), query, search_results)
                web_content = organize_mixed_list_categories(web_content, query, search_results)
                message = {
                    **message,
                    "content": web_content,
                }
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "message": message,
                    "model": response.get("model", payload["model"]),
                    "task": "translation" if is_translation_task else "coding" if is_coding_task else "chat",
                    "done": response.get("done", True),
                    "search": {
                        "enabled": use_web_search,
                        "results": answer_search_results,
                        "error": search_error,
                        "channels": internet_layer_channels,
                        "diagnostics": search_diagnostics,
                    },
                },
            )
        except (BrokenPipeError, ConnectionResetError):
            return
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            json_response(self, exc.code, {"ok": False, "error": friendly_ollama_error(error_body)})
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

    def handle_model_pull(self) -> None:
        try:
            body = read_json_body(self)
            result = start_model_pull(str(body.get("model", "")).strip())
            json_response(self, 200, result)
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})

    def handle_model_remove(self) -> None:
        try:
            body = read_json_body(self)
            result = remove_model(str(body.get("model", "")).strip())
            json_response(self, 200, result)
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})

    def handle_llm_check(self) -> None:
        try:
            body = read_json_body(self)
            base_url = normalize_local_llm_base_url(str(body.get("url") or ""))
            version = ollama_json("/api/version", timeout=5, base_url=base_url)
            tags = ollama_json("/api/tags", timeout=5, base_url=base_url)
            models = [
                str(item.get("name"))
                for item in tags.get("models", [])
                if isinstance(item, dict) and item.get("name")
            ]
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "url": base_url,
                    "version": version.get("version", ""),
                    "models": models,
                },
            )
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})

    def handle_asr_transcribe(self) -> None:
        try:
            body = read_json_body(self)
            model = normalize_asr_model(str(body.get("model") or ASR_MODEL or DEFAULT_ASR_MODEL))
            audio_base64 = str(body.get("audioBase64") or "").strip()
            mime_type = str(body.get("mimeType") or "audio/webm").strip()
            result = run_asr_transcription(audio_base64, mime_type, model)
            json_response(self, 200, result)
        except RuntimeError as exc:
            json_response(self, 501, {"ok": False, "error": str(exc), "asr": asr_status_payload()})
        except ValueError as exc:
            json_response(self, 400, {"ok": False, "error": str(exc), "asr": asr_status_payload()})
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})

    def handle_asr_setup(self) -> None:
        try:
            json_response(self, 200, start_asr_setup())
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc), "setup": asr_setup_status()})

    def handle_ocr_setup(self) -> None:
        try:
            json_response(self, 200, start_ocr_setup())
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc), "setup": ocr_setup_status()})

    def handle_internet_layer_setup(self) -> None:
        try:
            json_response(self, 200, start_internet_layer_setup())
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc), "setup": internet_layer_setup_status()})

    def handle_attachment_read(self) -> None:
        try:
            body = read_json_body(self)
            result = read_attached_file(
                str(body.get("name") or ""),
                str(body.get("mime") or ""),
                str(body.get("base64") or ""),
            )
            json_response(self, 200, {"ok": True, **result})
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})

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

    def handle_person_photo_upload(self) -> None:
        try:
            body = read_json_body(self)
            payload = person_photo_upload_payload(
                str(body.get("name") or ""),
                str(body.get("mime") or ""),
                str(body.get("base64") or ""),
            )
            json_response(self, 200 if payload.get("ok") else 400, payload)
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})

    def handle_person_photo_view(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query)
            file_name = Path((params.get("file") or [""])[0]).name
            if not file_name:
                self.send_error(404)
                return
            root = PERSON_PHOTO_DIR.resolve()
            path = (PERSON_PHOTO_DIR / file_name).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                self.send_error(404)
                return
            if not path.is_file():
                self.send_error(404)
                return
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            if content_type not in PERSON_PHOTO_MIME_EXTENSIONS:
                self.send_error(415)
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})

    def handle_workspace_preview(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query)
            root = params.get("root", [""])[0]
            relative_path = params.get("path", [""])[0]
            path = resolve_workspace_file(root, relative_path)
            if not path.exists() or not path.is_file():
                self.send_error(404)
                return
            if not is_probably_text(path):
                self.send_error(415)
                return
            content_type = mimetypes.guess_type(str(path))[0] or "text/plain"
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_knowledge_status(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query)
            folder_id = str(params.get("folderId", [""])[0]).strip()
            if not folder_id:
                json_response(self, 400, {"ok": False, "error": "folderId is required"})
                return
            json_response(self, 200, knowledge_status(db_path=KNOWLEDGE_DB_PATH, folder_id=folder_id))
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_knowledge(self) -> None:
        try:
            body = read_json_body(self)
            folder_id = str(body.get("folderId", "")).strip()
            if not folder_id:
                json_response(self, 400, {"ok": False, "error": "folderId is required"})
                return
            if self.path == "/api/knowledge/index":
                root_path = resolve_workspace_root(str(body.get("path", "")))
                result = index_knowledge_folder(
                    db_path=KNOWLEDGE_DB_PATH,
                    folder_id=folder_id,
                    root_path=root_path,
                    extract_text=extract_knowledge_text,
                    force=bool(body.get("force", False)),
                )
                json_response(self, 200, result)
            elif self.path == "/api/knowledge/search":
                result = search_knowledge(
                    db_path=KNOWLEDGE_DB_PATH,
                    folder_id=folder_id,
                    query=str(body.get("query", "")),
                    limit=int(body.get("limit", 5)),
                )
                json_response(self, 200, result)
            else:
                self.send_error(404)
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_contracts_list(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query)
            folder_id = str(params.get("folderId", [""])[0]).strip()
            json_response(self, 200, {"ok": True, "contracts": list_contracts(CONTRACT_DB_PATH, folder_id)})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_contracts(self) -> None:
        try:
            body = read_json_body(self)
            if self.path == "/api/contracts/extract":
                folder_id = str(body.get("folderId", "")).strip()
                if not folder_id:
                    json_response(self, 400, {"ok": False, "error": "folderId is required"})
                    return
                query = str(body.get("query", "")).strip() or "契約期間 自動更新 解約通知 期限"
                search_data = search_knowledge(
                    db_path=KNOWLEDGE_DB_PATH,
                    folder_id=folder_id,
                    query=query,
                    limit=int(body.get("limit", 5)),
                )
                snippets_by_path: dict[str, list[str]] = {}
                for item in search_data.get("results", [])[:5]:
                    source_path = str(item.get("path", "")).strip()
                    snippet = str(item.get("snippet", "")).strip()
                    if source_path and snippet:
                        snippets_by_path.setdefault(source_path, []).append(snippet)
                candidates = [
                    extract_contract_candidate(folder_id, source_path, "\n".join(snippets))
                    for source_path, snippets in snippets_by_path.items()
                ]
                json_response(self, 200, {
                    "ok": True,
                    "query": query,
                    "results": search_data.get("results", []),
                    "candidates": candidates,
                })
                return
            if self.path == "/api/contracts/import-gaps":
                folder_id = str(body.get("folderId", "")).strip()
                root = str(body.get("root", "")).strip()
                if not folder_id:
                    json_response(self, 400, {"ok": False, "error": "folderId is required"})
                    return
                if not root:
                    json_response(self, 400, {"ok": False, "error": "root is required"})
                    return
                json_response(self, 200, contract_import_gap_payload(root, folder_id))
                return
            if self.path == "/api/contracts/save":
                saved = save_contract(CONTRACT_DB_PATH, body.get("contract", body))
                json_response(self, 200, {"ok": True, "contract": saved})
                return
            if self.path == "/api/contracts/delete":
                json_response(self, 200, delete_contract(CONTRACT_DB_PATH, str(body.get("id", ""))))
                return
            self.send_error(404)
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_search(self) -> None:
        try:
            body = read_json_body(self)
            query = str(body.get("query", ""))
            results = search_web(query, int(body.get("max_results", 4)))
            json_response(self, 200, {"ok": True, "query": query, "results": results})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def handle_weather(self) -> None:
        try:
            body = read_json_body(self)
            query = str(body.get("query") or "")
            explicit_location = str(body.get("location") or "")
            parsed_location = weather_location_from_query(query) if query else ""
            location, day_offset = weather_request_parts(query, explicit_location)
            coordinates = body.get("coordinates") if not parsed_location and not explicit_location.strip() else None
            weather = fetch_weather(location, day_offset, coordinates)
            json_response(self, 200, {"ok": True, "answer": build_weather_answer(weather), "weather": weather})
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
            elif self.path == "/api/workspace/search":
                result = search_workspace_files(str(body.get("root", "")), str(body.get("query", "")))
                json_response(self, 200, {"ok": True, **result})
            elif self.path == "/api/workspace/write":
                result = write_workspace_file(
                    str(body.get("root", "")),
                    str(body.get("path", "")),
                    str(body.get("content", "")),
                )
                json_response(self, 200, {"ok": True, **result})
            elif self.path == "/api/workspace/reveal":
                result = reveal_workspace_path(str(body.get("root", "")), str(body.get("path", "")))
                json_response(self, 200, {"ok": True, **result})
            elif self.path == "/api/workspace/validate":
                result = validate_workspace_files(str(body.get("root", "")), body.get("files", []))
                json_response(self, 200, result)
            elif self.path == "/api/workspace/codegraph/init":
                result = build_codegraph_summary(str(body.get("root", "")))
                json_response(self, 200, {"ok": True, **result})
            elif self.path == "/api/workspace/codegraph/read":
                summary = read_codegraph_summary(str(body.get("root", "")))
                json_response(self, 200, {"ok": True, "summary": summary})
            else:
                self.send_error(404)
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="TOMOS AI local Web UI")
    parser.add_argument("--host", default=os.environ.get("GEMMA_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GEMMA_WEB_PORT", "54876")))
    parser.add_argument("--open", action="store_true", help="Open the Web UI in the default browser")
    parser.add_argument("--static-only", action="store_true", help="Serve PWA/static assets only and block write APIs")
    parser.add_argument("--mobile-sync-only", action="store_true", help="Serve static assets and only mobile sync APIs")
    args = parser.parse_args()

    Handler.static_only = args.static_only
    Handler.mobile_sync_only = args.mobile_sync_only
    address = (args.host, args.port)
    httpd = ThreadingHTTPServer(address, Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"TOMOS AI Web UI: {url}")
    if args.static_only or args.mobile_sync_only:
        print("Mode: mobile sync only" if args.mobile_sync_only else "Mode: mobile static preview (write APIs blocked)")
        for preview_url in mobile_preview_urls(args.port):
            print(f"Mobile preview URL: {preview_url}")
    print(f"App version: {APP_VERSION} ({app_commit() or 'no-git'})")
    print(f"Ollama: {OLLAMA_URL}")
    print(f"ComfyUI: {COMFYUI_URL}")
    print(f"Model: {MODEL}")
    print(f"Coding model: {select_coding_model()}")
    print(f"Translation model: {TRANSLATION_MODEL or 'auto'}")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")


if __name__ == "__main__":
    main()
