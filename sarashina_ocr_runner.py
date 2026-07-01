from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from pdf_reader import clamp_pdf_page_number, ocr_capabilities


ROOT = Path(__file__).resolve().parent
MODEL_ID = "sbintuitions/sarashina2.2-ocr"
MODEL_LABEL = "Sarashina2.2 OCR"
REQUIRED_MODULES = {
    "torch": "torch",
    "transformers": "transformers",
    "accelerate": "accelerate",
    "sentencepiece": "sentencepiece",
    "protobuf": "google.protobuf",
    "Pillow": "PIL",
}


def sarashina_python() -> Path:
    configured = os.environ.get("GEMMA_SARASHINA_PYTHON", "").strip()
    if configured:
        return Path(configured).expanduser()
    return ROOT / ".venv-ocr" / "bin" / "python"


def _module_available(module_name: str, python_path: Path | None = None) -> bool:
    if python_path is None:
        return importlib.util.find_spec(module_name) is not None
    if not python_path.exists():
        return False
    code = f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec({module_name!r}) else 1)"
    try:
        result = subprocess.run(
            [str(python_path), "-c", code],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def _cached_model_present(model_id: str = MODEL_ID) -> bool:
    cache_names = [
        f"models--{model_id.replace('/', '--')}",
        model_id.replace("/", "--"),
    ]
    cache_roots = [
        Path.home() / ".cache" / "huggingface" / "hub",
        Path.home() / ".cache" / "huggingface" / "transformers",
    ]
    for root in cache_roots:
        for name in cache_names:
            candidate = root / name
            if candidate.exists() and (
                any(candidate.rglob("*.safetensors"))
                or any(candidate.rglob("pytorch_model*.bin"))
            ):
                return True
    return False


def sarashina_ocr_status() -> dict[str, object]:
    python_path = sarashina_python()
    missing = [
        label
        for label, module_name in REQUIRED_MODULES.items()
        if not _module_available(module_name, python_path)
    ]
    model_cached = _cached_model_present()
    runner_exists = python_path.exists()
    available = runner_exists and not missing and model_cached
    if not runner_exists:
        status = "needs_runner"
        note = "Sarashina OCR用のPython環境 .venv-ocr が見つかりません。"
    elif missing:
        status = "needs_dependencies"
        note = "Sarashina OCRを試すには、Python依存ライブラリの導入が必要です。"
    elif not model_cached:
        status = "needs_model_download"
        note = "Sarashina OCRを試すには、モデルのローカル取得が必要です。"
    else:
        status = "ready"
        note = "Sarashina OCRのローカル比較を試せます。"
    return {
        "ok": True,
        "id": "sarashina2.2-ocr",
        "label": MODEL_LABEL,
        "model": MODEL_ID,
        "available": available,
        "status": status,
        "runnerPython": str(python_path),
        "missing": missing,
        "modelCached": model_cached,
        "requiresDownload": not model_cached,
        "externalApi": False,
        "note": note,
    }


def sarashina_compare_page_payload(source_path: str, page: object = 1) -> dict[str, object]:
    path = Path(str(source_path or "").strip()).expanduser().resolve()
    page_number = clamp_pdf_page_number(page)
    status = sarashina_ocr_status()
    if not source_path:
        return {"ok": False, "error": "PDFファイルのパスを入力してください。", "sarashina": status}
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": "PDFファイルが見つかりません。", "sarashina": status}
    if path.suffix.lower() != ".pdf":
        return {"ok": False, "error": "PDFファイルを指定してください。", "sarashina": status}
    if not status.get("available"):
        return {
            "ok": False,
            "error": str(status.get("note") or "Sarashina OCRは未準備です。"),
            "sarashina": status,
        }
    image_path = _render_pdf_page_to_png(path, page_number)
    started_at = time.time()
    runner_script = ROOT / "scripts" / "sarashina_ocr_page.py"
    try:
        result = subprocess.run(
            [
                str(sarashina_python()),
                str(runner_script),
                "--image",
                str(image_path),
                "--model",
                MODEL_ID,
                "--max-new-tokens",
                "800",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            check=False,
        )
    finally:
        try:
            image_path.unlink(missing_ok=True)
        except Exception:
            pass
    elapsed = round(time.time() - started_at, 1)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    payload = _parse_runner_json(stdout)
    if payload is None:
        payload = {"ok": False, "error": stdout or stderr or "sarashina_runner_no_output"}
    if result.returncode != 0 or not payload.get("ok"):
        return {
            "ok": False,
            "error": str(payload.get("error") or stderr or "Sarashina OCRの実行に失敗しました。"),
            "sarashina": status,
            "stderr": stderr[-1200:],
            "elapsedSeconds": elapsed,
        }
    text = str(payload.get("text") or "").strip()
    return {
        "ok": True,
        "pdfImportId": "contract-pdf-import",
        "runner": "sarashina2.2-ocr",
        "runnerLabel": MODEL_LABEL,
        "sourcePath": str(path),
        "page": page_number,
        "textLength": len(text),
        "preview": text[:2000],
        "fullText": text,
        "elapsedSeconds": elapsed,
        "sarashina": status,
        "message": "Sarashina OCRで1ページを読み取りました。",
    }


def _render_pdf_page_to_png(path: Path, page_number: int) -> Path:
    capabilities = ocr_capabilities()
    pdftoppm_binary = str(capabilities.get("pdftoppm") or shutil.which("pdftoppm") or "")
    if not pdftoppm_binary:
        raise RuntimeError("PDFを画像化するためのPoppler(pdftoppm)が見つかりません。")
    tmp_dir = Path(tempfile.mkdtemp(prefix="gemma4-sarashina-page-"))
    output_prefix = tmp_dir / "page"
    result = subprocess.run(
        [
            pdftoppm_binary,
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-r",
            "120",
            "-png",
            str(path),
            str(output_prefix),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    images = sorted(tmp_dir.glob("page-*.png"))
    if result.returncode != 0 or not images:
        raise RuntimeError((result.stderr or result.stdout or "PDFページを画像化できませんでした。").strip())
    return images[0]


def _parse_runner_json(stdout: str) -> dict[str, object] | None:
    text = (stdout or "").strip()
    if not text:
        return None
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else None
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        cleaned = line.strip()
        if not cleaned.startswith("{"):
            continue
        try:
            loaded = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        return loaded if isinstance(loaded, dict) else None
    return None
