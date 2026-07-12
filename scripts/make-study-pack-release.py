#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_SOURCE = ROOT / "study-packs" / "note-article-writing-pack"
ARCHIVE_ROOT = "note-article-writing-pack"
FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def build_archive(output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(path for path in PACK_SOURCE.rglob("*") if path.is_file()):
            relative = source.relative_to(PACK_SOURCE).as_posix()
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{relative}", FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compresslevel=9)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="note記事作成サポートの配布ZIPを生成します。")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "TOMOS-note-article-writing-v0.1.0.zip",
    )
    args = parser.parse_args()
    digest = build_archive(args.output)
    print(f"{digest}  {args.output}")


if __name__ == "__main__":
    main()
