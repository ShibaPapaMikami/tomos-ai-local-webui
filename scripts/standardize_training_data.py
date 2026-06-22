#!/usr/bin/env python3
"""Normalize Gemma4_12B chat exports into messages JSONL.

The Web UI exports one JSON object per line:
{"messages": [...], "metadata": {...}}

Most fine-tuning trainers only need the messages field. This script validates
the conversation shape, drops empty/error examples, and writes clean JSONL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_ROLES = {"system", "user", "assistant"}
ERROR_PREFIXES = ("エラー", "生成エラー", "保存エラー", "Error", "Request failed", "timed out")


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_messages(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    messages: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            return []
        role = clean_text(item.get("role"))
        content = clean_text(item.get("content"))
        if role not in ALLOWED_ROLES or not content:
            return []
        messages.append({"role": role, "content": content})
    if len(messages) < 2:
        return []
    if not any(message["role"] == "user" for message in messages):
        return []
    if not any(message["role"] == "assistant" for message in messages):
        return []
    assistant = next((message["content"] for message in reversed(messages) if message["role"] == "assistant"), "")
    if assistant.startswith(ERROR_PREFIXES):
        return []
    return messages


def normalize_line(line: str, keep_metadata: bool) -> dict[str, Any] | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    messages = normalize_messages(payload.get("messages") if isinstance(payload, dict) else None)
    if not messages:
        return None
    if keep_metadata:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        return {"messages": messages, "metadata": metadata}
    return {"messages": messages}


def standardize(input_path: Path, output_path: Path, keep_metadata: bool) -> tuple[int, int]:
    total = 0
    kept = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as output:
        for line in source:
            if not line.strip():
                continue
            total += 1
            normalized = normalize_line(line, keep_metadata)
            if not normalized:
                continue
            output.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            kept += 1
    return total, kept


def main() -> int:
    parser = argparse.ArgumentParser(description="Standardize Gemma4_12B training JSONL exports.")
    parser.add_argument("input", type=Path, help="Exported JSONL from the Web UI")
    parser.add_argument("-o", "--output", type=Path, help="Output JSONL path")
    parser.add_argument("--keep-metadata", action="store_true", help="Keep metadata for filtering/debugging")
    args = parser.parse_args()

    output = args.output or args.input.with_suffix(".standardized.jsonl")
    total, kept = standardize(args.input, output, args.keep_metadata)
    print(f"read={total} kept={kept} output={output}")
    return 0 if kept > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
