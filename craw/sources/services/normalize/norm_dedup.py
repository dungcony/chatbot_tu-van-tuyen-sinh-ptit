#!/usr/bin/env python3
"""
Xử lý: Deduplication.
Trường hợp: Nhiều trang đăng lại cùng nội dung, tránh lưu trùng.
"""
import hashlib
import re


def content_hash(text: str) -> str:
    """
    MD5 hash của nội dung (chuẩn hóa khoảng trắng để so sánh).
    """
    normalized = re.sub(r"\s+", " ", text.strip())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()
