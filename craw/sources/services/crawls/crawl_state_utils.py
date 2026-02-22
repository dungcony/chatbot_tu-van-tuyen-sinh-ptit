#!/usr/bin/env python3
"""
Tiện ích quản lý trạng thái crawl (crawled, failed).
- Đọc, ghi trạng thái crawl
"""
import json
from pathlib import Path


def load_state(state_file: Path) -> dict:
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"crawled": [], "failed": []}


def save_state(state_file: Path, state: dict):
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
