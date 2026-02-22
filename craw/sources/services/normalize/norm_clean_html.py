#!/usr/bin/env python3
"""
Xử lý: HTML & ký tự đặc biệt.
Trường hợp: Thẻ HTML còn sót, &nbsp;, khoảng trắng thừa.
"""
import re
import html


def clean_html_and_special_chars(text: str) -> str:
    """
    - Decode HTML entities (&nbsp; -> space)
    - Xóa thẻ HTML còn sót
    - Chuẩn hóa khoảng trắng
    """
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s+|\s+$", "", text)
    return text
