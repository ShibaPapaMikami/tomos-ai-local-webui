from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MAX_OCR_PDF_PAGES = 3


def available_tesseract_languages(tesseract_binary: str) -> list[str]:
    if not tesseract_binary:
        return []
    try:
        result = subprocess.run(
            [tesseract_binary, "--list-langs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    languages: list[str] = []
    for line in (result.stdout or "").splitlines():
        value = line.strip()
        if not value or value.lower().startswith("list of available languages"):
            continue
        languages.append(value)
    return languages


def preferred_ocr_language(languages: list[str]) -> str:
    available = set(languages)
    if {"jpn", "eng"}.issubset(available):
        return "jpn+eng"
    if "jpn" in available:
        return "jpn"
    if "eng" in available:
        return "eng"
    return languages[0] if languages else "eng"


def ocr_capabilities() -> dict[str, object]:
    tesseract_binary = shutil.which("tesseract") or ""
    pdftoppm_binary = shutil.which("pdftoppm") or ""
    languages = available_tesseract_languages(tesseract_binary)
    language = preferred_ocr_language(languages)
    image_available = bool(tesseract_binary)
    pdf_available = bool(tesseract_binary and pdftoppm_binary)
    missing: list[str] = []
    if not tesseract_binary:
        missing.append("Tesseract")
    if not pdftoppm_binary:
        missing.append("Poppler(pdftoppm)")
    return {
        "available": image_available or pdf_available,
        "image": image_available,
        "pdf": pdf_available,
        "engine": "Tesseract" if tesseract_binary else "",
        "tesseract": tesseract_binary,
        "pdftoppm": pdftoppm_binary,
        "language": language,
        "languages": languages[:24],
        "missing": missing,
    }


def clamp_pdf_page_number(value: object) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(page, 100))


def pdf_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader  # type: ignore

        return len(PdfReader(str(path)).pages)
    except Exception:
        return 0


def extract_pdf_page_text(path: Path, page: int = 1) -> str:
    page_number = clamp_pdf_page_number(page)
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return (
            usable_pdf_text(extract_pdf_text_with_pdftotext(path, page_number))
            or extract_pdf_text_with_mdls(path)
            or extract_pdf_text_from_streams(path)
            or extract_pdf_ocr_text(path)
        )
    try:
        reader = PdfReader(str(path))
        if page_number > len(reader.pages):
            return ""
        text = (reader.pages[page_number - 1].extract_text() or "").strip()
        return (
            usable_pdf_text(text)
            or usable_pdf_text(extract_pdf_text_with_pdftotext(path, page_number))
            or extract_pdf_text_with_mdls(path)
            or extract_pdf_text_from_streams(path)
            or extract_pdf_ocr_text(path)
        )
    except Exception:
        return (
            usable_pdf_text(extract_pdf_text_with_pdftotext(path, page_number))
            or extract_pdf_text_with_mdls(path)
            or extract_pdf_text_from_streams(path)
            or extract_pdf_ocr_text(path)
        )


def extract_image_ocr_text(path: Path) -> str:
    capabilities = ocr_capabilities()
    tesseract_binary = str(capabilities.get("tesseract") or "")
    if not tesseract_binary:
        return ""
    try:
        result = subprocess.run(
            [
                tesseract_binary,
                str(path),
                "stdout",
                "-l",
                str(capabilities.get("language") or "eng"),
                "--psm",
                "6",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    text = (result.stdout or "").strip()
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def extract_pdf_ocr_text(path: Path) -> str:
    capabilities = ocr_capabilities()
    pdftoppm_binary = str(capabilities.get("pdftoppm") or "")
    if not pdftoppm_binary or not capabilities.get("pdf"):
        return ""
    texts: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="gemma4-pdf-ocr-") as tmp_dir:
            output_prefix = Path(tmp_dir) / "page"
            result = subprocess.run(
                [
                    pdftoppm_binary,
                    "-f",
                    "1",
                    "-l",
                    str(MAX_OCR_PDF_PAGES),
                    "-r",
                    "180",
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
            if result.returncode != 0:
                return ""
            for image_path in sorted(Path(tmp_dir).glob("page-*.png"))[:MAX_OCR_PDF_PAGES]:
                text = extract_image_ocr_text(image_path)
                if text:
                    texts.append(text)
    except Exception:
        return ""
    return "\n\n".join(texts).strip()


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        text = extract_pdf_text_with_pdftotext(path)
        return (
            usable_pdf_text(text)
            or extract_pdf_text_with_mdls(path)
            or extract_pdf_text_from_streams(path)
            or extract_pdf_ocr_text(path)
        )
    try:
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
        return (
            usable_pdf_text(text)
            or extract_pdf_text_with_mdls(path)
            or extract_pdf_text_from_streams(path)
            or extract_pdf_ocr_text(path)
        )
    except Exception:
        text = extract_pdf_text_with_pdftotext(path)
        return (
            usable_pdf_text(text)
            or extract_pdf_text_with_mdls(path)
            or extract_pdf_text_from_streams(path)
            or extract_pdf_ocr_text(path)
        )


def extract_pdf_text_with_pdftotext(path: Path, page: int | None = None) -> str:
    binary = shutil.which("pdftotext")
    if not binary:
        return ""
    command = [binary, "-layout"]
    if page is not None:
        page_number = clamp_pdf_page_number(page)
        command.extend(["-f", str(page_number), "-l", str(page_number)])
    command.extend([str(path), "-"])
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def extract_pdf_text_with_mdls(path: Path) -> str:
    binary = shutil.which("mdls")
    if not binary:
        return ""
    try:
        result = subprocess.run(
            [binary, "-raw", "-name", "kMDItemTextContent", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    text = (result.stdout or "").strip()
    if not text or text == "(null)":
        return ""
    return text


def decode_pdf_string(value: bytes) -> str:
    if not value:
        return ""
    value = re.sub(rb"\\([nrtbf()\\])", lambda match: {
        b"n": b"\n",
        b"r": b"\r",
        b"t": b"\t",
        b"b": b"\b",
        b"f": b"\f",
        b"(": b"(",
        b")": b")",
        b"\\": b"\\",
    }.get(match.group(1), match.group(1)), value)
    if value.startswith(b"\xfe\xff"):
        try:
            return value[2:].decode("utf-16-be", errors="ignore")
        except Exception:
            pass
    for encoding in ("utf-8", "shift_jis", "latin-1"):
        try:
            return value.decode(encoding, errors="ignore")
        except Exception:
            continue
    return ""


def decode_pdf_hex_string(value: bytes) -> str:
    cleaned = re.sub(rb"\s+", b"", value)
    if len(cleaned) % 2:
        cleaned += b"0"
    try:
        raw = bytes.fromhex(cleaned.decode("ascii"))
    except Exception:
        return ""
    return decode_pdf_string(raw)


def usable_pdf_text(text: str) -> str:
    text = (text or "").strip()
    return text if pdf_text_looks_readable(text) else ""


def pdf_text_looks_readable(text: str) -> bool:
    sample = re.sub(r"\s+", "", text or "")
    if len(sample) < 20:
        return False
    cjk_count = len(re.findall(r"[ぁ-んァ-ヶ一-龠ー]", sample))
    cjk_ratio = cjk_count / max(len(sample), 1)
    symbols = len(re.findall(r"[#%+<>{}\\^_`|~]", sample))
    letters = len(re.findall(r"[A-Za-z]", sample))
    if symbols / max(len(sample), 1) > 0.08 and cjk_ratio < 0.08:
        return False
    if letters >= 40:
        words = re.findall(r"[A-Za-z]{3,}", text)
        long_words = [word for word in words if len(word) >= 6]
        word_text = "".join(long_words or words)
        vowel_count = len(re.findall(r"[AEIOUaeiou]", word_text))
        if word_text and vowel_count / max(len(word_text), 1) < 0.18 and cjk_ratio < 0.2:
            return False
    if cjk_count >= 10 and cjk_ratio > 0.05:
        return True
    return True


def extract_pdf_text_from_streams(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except Exception:
        return ""
    chunks: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, flags=re.S):
        chunk = match.group(1)
        try:
            chunk = zlib.decompress(chunk)
        except Exception:
            pass
        chunks.append(chunk)
    chunks.append(raw)
    texts: list[str] = []
    for chunk in chunks:
        for match in re.finditer(rb"\((?:\\.|[^\\)]){2,}\)", chunk, flags=re.S):
            value = match.group(0)[1:-1]
            text = decode_pdf_string(value).strip()
            if text:
                texts.append(text)
        for match in re.finditer(rb"<([0-9A-Fa-f\s]{4,})>", chunk):
            text = decode_pdf_hex_string(match.group(1)).strip()
            if text:
                texts.append(text)
    text = "\n".join(texts)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not pdf_text_looks_readable(text):
        return ""
    return text
