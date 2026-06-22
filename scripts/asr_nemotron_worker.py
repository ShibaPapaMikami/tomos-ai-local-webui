#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import shutil
import sys
from pathlib import Path

from asr_nemotron_runner import ensure_wav, normalize_transcription


class NemotronWorker:
    def __init__(self) -> None:
        self.model_name = ""
        self.asr_model = None

    def load_model(self, model_name: str):
        if self.asr_model is not None and self.model_name == model_name:
            return self.asr_model
        import nemo.collections.asr as nemo_asr

        self.asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_name)
        self.model_name = model_name
        return self.asr_model

    def transcribe(self, request: dict) -> dict:
        audio_path = Path(str(request.get("audio") or "")).expanduser().resolve()
        model_name = str(request.get("model") or "nvidia/nemotron-3.5-asr-streaming-0.6b")
        mime_type = str(request.get("mimeType") or request.get("mime_type") or "audio/webm")
        language = str(request.get("language") or "ja-JP")
        if not audio_path.exists():
            raise RuntimeError(f"音声ファイルが見つかりません: {audio_path}")

        wav_path, temp_dir = ensure_wav(audio_path, mime_type)
        try:
            asr_model = self.load_model(model_name)
            transcribe_config = asr_model.get_transcribe_config()
            transcribe_config.batch_size = 1
            transcribe_config.num_workers = 0
            transcribe_config.use_lhotse = False
            if hasattr(transcribe_config, "target_lang"):
                transcribe_config.target_lang = language
            try:
                transcription = asr_model.transcribe([str(wav_path)], override_config=transcribe_config)
            except TypeError:
                transcription = asr_model.transcribe([str(wav_path)], target_lang=language)
            text = normalize_transcription(transcription)
            if not text:
                raise RuntimeError("文字起こし結果が空でした。")
            return {"ok": True, "text": text, "model": model_name, "language": language}
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)


def write_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def main() -> int:
    worker = NemotronWorker()
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            request = json.loads(raw_line)
            with contextlib.redirect_stdout(sys.stderr):
                payload = worker.transcribe(request)
            write_json(payload)
        except Exception as exc:
            write_json({"ok": False, "error": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
