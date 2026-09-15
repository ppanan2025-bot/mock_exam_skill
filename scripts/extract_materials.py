#!/usr/bin/env python3
"""Extract text from lecture slides, past papers, and tutorial files.

Supports PDF (pypdf), PPTX/DOCX (stdlib ZIP+XML), and plain text.
Prints a JSON array to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tex"}
SKIP_NAMES = {".gitkeep", ".ds_store"}
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _record(
    path: Path,
    kind: str,
    text: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "type": kind,
        "chars": len(text),
        "empty": not bool(text.strip()),
        "text": text.strip(),
    }
    if extra:
        rec.update(extra)
    return rec


def extract_pdf(path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            json.dumps(
                {
                    "ok": False,
                    "errors": [
                        "pypdf is required for PDFs. Install with: python -m pip install pypdf"
                    ],
                }
            )
        ) from exc
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n\n".join(pages)
    scanned = bool(reader.pages) and not text.strip()
    return _record(
        path,
        "pdf",
        text,
        {
            "pages": len(reader.pages),
            "likely_scanned": scanned,
        },
    )


def _zip_xml_texts(path: Path, inner_glob: str, tag: str) -> str:
    chunks: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist() if n.startswith(inner_glob) and n.endswith(".xml"))
        for name in names:
            root = ET.fromstring(zf.read(name))
            parts = [el.text for el in root.iter(tag) if el.text]
            if parts:
                chunks.append("\n".join(parts))
    return "\n\n".join(chunks)


def extract_pptx(path: Path) -> dict[str, Any]:
    text = _zip_xml_texts(path, "ppt/slides/slide", f"{A_NS}t")
    return _record(path, "pptx", text)


def extract_docx(path: Path) -> dict[str, Any]:
    text = _zip_xml_texts(path, "word/document", f"{W_NS}t")
    return _record(path, "docx", text)


def extract_text(path: Path) -> dict[str, Any]:
    return _record(path, path.suffix.lstrip(".") or "text", path.read_text(encoding="utf-8", errors="replace"))


def extract_one(path: Path) -> dict[str, Any] | None:
    suffix = path.suffix.lower()
    if path.name.lower() in SKIP_NAMES:
        return None
    try:
        if suffix == ".pdf":
            return extract_pdf(path)
        if suffix == ".pptx":
            return extract_pptx(path)
        if suffix == ".docx":
            return extract_docx(path)
        if suffix in TEXT_SUFFIXES:
            return extract_text(path)
    except Exception as exc:  # noqa: BLE001 — report per-file failures to the agent
        return _record(path, suffix.lstrip(".") or "unknown", "", {"error": str(exc)})
    return _record(
        path,
        suffix.lstrip(".") or "unsupported",
        "",
        {
            "skipped": True,
            "note": "Unsupported type. Use vision_analyze for images, or convert first.",
        },
    )


def iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = [p for p in root.rglob("*") if p.is_file() and p.name.lower() not in SKIP_NAMES]
    files.sort()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories of slides / past papers / tutorials",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=0,
        help="If >0, truncate each file's text to this many characters",
    )
    args = parser.parse_args()

    records: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw in args.paths:
        path = raw.expanduser()
        if not path.exists():
            missing.append(str(path))
            continue
        for file_path in iter_files(path):
            rec = extract_one(file_path)
            if rec is None:
                continue
            if args.max_chars and len(rec.get("text") or "") > args.max_chars:
                rec["text"] = rec["text"][: args.max_chars] + "\n[truncated]"
                rec["truncated"] = True
            records.append(rec)

    payload = {
        "ok": not missing,
        "files": len(records),
        "missing": missing,
        "records": records,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
