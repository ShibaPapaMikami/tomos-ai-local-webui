#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def write_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def ensure_wav(audio_path: Path, mime_type: str) -> tuple[Path, Path | None]:
    clean_mime = (mime_type or "").split(";")[0].strip().lower()
    if clean_mime in {"audio/wav", "audio/wave", "audio/x-wav"} or audio_path.suffix.lower() == ".wav":
        return audio_path, None

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "Nemotron ASRはWAV入力が前提です。ブラウザ録音を変換するためにffmpegをインストールしてください。"
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="gemma4-asr-"))
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
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpegで音声をWAVへ変換できませんでした。")
    return wav_path, temp_dir


def normalize_transcription(value: object) -> str:
    def clean(text: str) -> str:
        text = text.strip()
        text = " ".join(text.replace("\n", " ").split())
        text = text.replace("<ja-JP>", "").replace("<ja-JA>", "").replace("<auto>", "")
        text = " ".join(text.split())
        return text.strip()

    if isinstance(value, str):
        return clean(value)
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str):
            return clean(first)
        if isinstance(first, dict):
            return clean(str(first.get("text") or first.get("pred_text") or ""))
        text = getattr(first, "text", "")
        if text:
            return clean(str(text))
    if isinstance(value, tuple) and value:
        return normalize_transcription(value[0])
    text = getattr(value, "text", "")
    if text:
        return clean(str(text))
    return ""


def run(args: argparse.Namespace) -> dict:
    try:
        import nemo.collections.asr as nemo_asr
    except Exception as exc:
        raise RuntimeError(
            "NVIDIA NeMoが未導入です。python>=3.11、PyTorch、Cython、packaging、"
            "nemo_toolkit[asr] を導入してから再実行してください。"
        ) from exc

    audio_path = Path(args.audio).expanduser().resolve()
    if not audio_path.exists():
        raise RuntimeError(f"音声ファイルが見つかりません: {audio_path}")

    wav_path, temp_dir = ensure_wav(audio_path, args.mime_type)
    try:
        asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=args.model)
        transcribe_config = asr_model.get_transcribe_config()
        transcribe_config.batch_size = 1
        transcribe_config.num_workers = 0
        transcribe_config.use_lhotse = False
        if hasattr(transcribe_config, "target_lang"):
            transcribe_config.target_lang = args.language
        try:
            transcription = asr_model.transcribe([str(wav_path)], override_config=transcribe_config)
        except TypeError:
            transcription = asr_model.transcribe([str(wav_path)], target_lang=args.language)
        text = normalize_transcription(transcription)
        if not text:
            raise RuntimeError("文字起こし結果が空でした。")
        return {
            "ok": True,
            "text": text,
            "model": args.model,
            "language": args.language,
        }
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Nemotron 3.5 ASR for Gemma 4 local UI.")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", default="nvidia/nemotron-3.5-asr-streaming-0.6b")
    parser.add_argument("--mime-type", default="audio/webm")
    parser.add_argument("--language", default="ja-JP")
    args = parser.parse_args()

    try:
        with contextlib.redirect_stdout(sys.stderr):
            payload = run(args)
        write_json(payload)
        return 0
    except Exception as exc:
        write_json({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
