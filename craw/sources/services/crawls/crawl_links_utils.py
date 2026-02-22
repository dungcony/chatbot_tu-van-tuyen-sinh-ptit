#!/usr/bin/env python3
"""
Tiện ích xử lý link crawl.
- Đọc, flatten link từ file JSON
- Quản lý trạng thái crawl
"""
import json
from pathlib import Path


def flatten_links_from_json(obj, base_key="") -> list[dict]:
    """
    Flatten cấu trúc JSON lồng nhau thành danh sách {url, category, key}.
    """
    result = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_path = f"{base_key}/{k}" if base_key else k
            result.extend(flatten_links_from_json(v, key_path))
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, str) and item.startswith("http"):
                result.append({"url": item, "category": base_key})
            else:
                result.extend(flatten_links_from_json(item, base_key))
    return result


def load_links_from_file(json_path: Path) -> list[dict]:
    """Đọc file JSON và flatten thành danh sách URL."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return flatten_links_from_json(data)


def load_all_links(links_dir: Path, source_filter: str | None = None) -> dict[str, list[dict]]:
    """
    Đọc tất cả file .json trong links/
    Trả về: {source_id: [{url, category}, ...]}
    """
    if not links_dir.exists():
        return {}

    result = {}
    for f in links_dir.glob("*.json"):
        source_id = f.stem
        if source_filter and source_id != source_filter:
            continue
        try:
            items = load_links_from_file(f)
            if items:
                result[source_id] = items
        except Exception as e:
            print(f"  WARN Không đọc được {f.name}: {e}")
    return result


def load_state(state_file: Path) -> dict:
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"crawled": [], "failed": []}


def save_state(state_file: Path, state: dict):
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
