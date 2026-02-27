#!/usr/bin/env python3
"""
Script chuẩn bị và upload dữ liệu đã normalize lên MongoDB.
Chạy: python scripts/prepare_data.py
"""
import os
import sys
import json
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from models.document import get_collection, SCHEMA

NOR_DIR = PROJECT_DIR / "nor"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 400
MIN_FINAL_CHUNK = CHUNK_SIZE // 2


def chunk_content(content, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Chia nội dung thành chunks với overlap. Chunk cuối gộp vào trước nếu <= min_final."""
    chunks = []
    lines = content.splitlines()
    buf, total = [], 0
    overlap_only = False
    for line in lines:
        buf.append(line)
        overlap_only = False
        total += len(line)
        if total >= chunk_size:
            chunks.append("\n".join(buf))
            overlap_chars, overlap_buf = 0, []
            for i in range(len(buf) - 1, -1, -1):
                overlap_buf.insert(0, buf[i])
                overlap_chars += len(buf[i])
                if overlap_chars >= overlap:
                    break
            buf, total = overlap_buf, overlap_chars
            overlap_only = True
    if buf and not overlap_only:
        remainder = "\n".join(buf)
        if total <= MIN_FINAL_CHUNK and chunks:
            chunks[-1] = chunks[-1] + "\n" + remainder
        else:
            chunks.append(remainder)
    return chunks


def extract_meta_from_file(filepath):
    """Đọc file .md đã normalize, tách meta và content."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()
    meta = {
        "school": None,
        "source_file": filepath.name,
        "source_url": None,
        "source_title": None,
        "tags": [],
        "year": None,
        "chunk_id": None,
        "total_chunks": None,
    }
    content = raw
    # Tách meta
    if "[TITLE]" in raw and "[URL]" in raw and "[META]" in raw:
        parts = raw.split("---", 1)
        header = parts[0]
        content = parts[1].strip() if len(parts) > 1 else raw
        lines = header.splitlines()
        for i, line in enumerate(lines):
            if line.strip() == "[TITLE]":
                meta["source_title"] = lines[i+1].strip()
            if line.strip() == "[URL]":
                meta["source_url"] = lines[i+1].strip()
            if line.strip() == "[META]":
                for j in range(i+1, min(i+6, len(lines))):
                    l = lines[j].strip()
                    if l.startswith("school:"):
                        meta["school"] = l.split(":",1)[1].strip()
                    if l.startswith("tags:"):
                        meta["tags"] = [t.strip() for t in l.split(":",1)[1].split(",") if t.strip()]
                    if l.startswith("year:"):
                        y = l.split(":", 1)[1].strip()
                        if y.isdigit():
                            meta["year"] = int(y)
                        else:
                            meta["year"] = y or None

    # Fallback: infer year from tags or filename
    if meta.get("year") in (None, ""):
        years = []
        for t in meta.get("tags") or []:
            if isinstance(t, str) and t.isdigit() and len(t) == 4:
                y = int(t)
                if 2015 <= y <= 2035:
                    years.append(y)
        if not years:
            for s in re.findall(r"\b(20\d{2})\b", meta.get("source_file") or ""):
                y = int(s)
                if 2015 <= y <= 2035:
                    years.append(y)
        meta["year"] = max(years) if years else None
    return meta, content


def prepare_and_upload():
    col = get_collection()
    files = sorted([f for f in NOR_DIR.glob("*.md") if f.is_file()])
    print(f"Đang upload {len(files)} file...")
    for f in files:
        meta, content = extract_meta_from_file(f)
        chunks = chunk_content(content)
        total_chunks = len(chunks)
        for idx, chunk in enumerate(chunks):
            doc = dict(SCHEMA)
            doc["content"] = chunk
            doc["school"] = meta["school"]
            doc["source_file"] = meta["source_file"]
            doc["source_url"] = meta["source_url"]
            doc["source_title"] = meta["source_title"]
            doc["tags"] = meta["tags"]
            doc["year"] = meta["year"]
            doc["chunk_id"] = idx + 1
            doc["total_chunks"] = total_chunks
            doc["embedding"] = None  # Chưa embed, sẽ cập nhật sau
            col.insert_one(doc)
        print(f"  OK: {f.name} ({total_chunks} chunks)")
    print("Hoàn thành upload dữ liệu lên MongoDB.")


if __name__ == "__main__":
    prepare_and_upload()
