#!/usr/bin/env python3
"""
Xử lý: Tách metadata header [Title] [URL: ...] và extract school.
Trường hợp: File crawl có format [Tiêu đề][URL: ...] ở đầu.
"""
import re


def extract_meta_header(text: str) -> tuple[str, str, str]:
    """
    Tách [Title] [URL: ...] khỏi nội dung.
    Trả về (content, source_url, source_title).
    """
    m = re.match(
        r"^(?:\[(?P<title>[^\]]+)\]\s*\n)?\[URL:\s*(?P<url>https?://\S+)\]\s*\n",
        text.lstrip(),
        re.MULTILINE
    )
    if m:
        url = m.group("url") or ""
        title = (m.group("title") or "").strip()
        content = text[m.end():].strip()
    else:
        url, title, content = "", "", text.strip()
    return content, url, title


def extract_school(filename: str) -> str:
    """ptit_trangchu.md -> ptit"""
    base = filename.replace(".md", "").replace(".txt", "")
    return base.split("_")[0] if "_" in base else "unknown"
