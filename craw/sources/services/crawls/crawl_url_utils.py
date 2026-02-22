#!/usr/bin/env python3
"""
Tiện ích xử lý URL và tên file crawl.
- Chuyển URL thành tên file an toàn
"""
import re
from urllib.parse import urlparse


def url_to_filename(source_id: str, url: str, suffix: str = "md") -> str:
    path = urlparse(url).path.strip("/").replace("/", "_") or "trangchu"
    safe = re.sub(r"[^\w\-]", "_", path)[:60]
    return f"{source_id}_{safe}.{suffix}"
