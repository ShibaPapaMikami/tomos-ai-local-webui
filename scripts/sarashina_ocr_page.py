#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import traceback
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sarashina2.2 OCR for one image page.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--model", default="sbintuitions/sarashina2.2-ocr")
    parser.add_argument("--max-new-tokens", type=int, default=1200)
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(json.dumps({"ok": False, "error": "image_not_found"}, ensure_ascii=False))
        return 2

    try:
        root = Path(__file__).resolve().parents[1]
        module_cache = root / ".gemma4-data" / "huggingface" / "modules"
        module_cache.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_MODULES_CACHE", str(module_cache))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        with contextlib.redirect_stdout(sys.stderr):
            import torch
            from PIL import Image
            from transformers import AutoModelForCausalLM, AutoProcessor, set_seed

            device = "mps" if torch.backends.mps.is_available() else "cpu"
            processor = AutoProcessor.from_pretrained(args.model, trust_remote_code=True, local_files_only=True)
            model = AutoModelForCausalLM.from_pretrained(
                args.model,
                torch_dtype="auto",
                trust_remote_code=True,
                local_files_only=True,
            )
            model.to(device)
            model.eval()
            set_seed(42)

            image = Image.open(image_path).convert("RGB")
            message = [
                {
                    "role": "user",
                    "content": [{"type": "image", "image": image}],
                }
            ]
            inputs = processor.apply_chat_template(
                message,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            ).to(device)
            with torch.inference_mode():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=max(64, min(args.max_new_tokens, 6000)),
                    do_sample=False,
                    repetition_penalty=1.2,
                    use_cache=True,
                )
            generated = output_ids[:, inputs["input_ids"].shape[-1]:]
            text = processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
        print(json.dumps({"ok": True, "text": text, "device": device}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc()[-2000:],
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
