#!/usr/bin/env python3
"""
Xử lý: Xóa menu nav, footer, dòng rác.
Trường hợp: Crawl về có block menu * / + / -, footer lặp, dòng spam.
"""
import re

FOOTER_MARKERS = [
    "ĐỊA CHỈ HỌC VIỆN",
    "THÔNG TIN LIÊN HỆ",
    "VỀ CHÚNG TÔI",
    "ĐƯỜNG DẪN",
    "© Copyright",
    "All rights reserved",
]

JUNK_LINES = {
    "xem chi tiết", "xem chi tiet", "facebook", "youtube",
    "admindaotao", "ptit",
}

_NAV_LINE = re.compile(r"^[\*\+\-]\s*(?:\[.+\]\(.+\)|.{0,50})\s*$")
_BULLET_PREFIX = re.compile(r"^[\*\+\-]\s*")


def _strip_bullet(line: str) -> str:
    """Strip bullet prefix (* / + / -) từ dòng."""
    return _BULLET_PREFIX.sub("", line.strip()).strip()


def normalize_empty_lines(text: str) -> str:
    """
    Loại bỏ tất cả dòng trống để data gọn, không loãng.
    """
    if not text:
        return ""
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines).strip()


def clean_content(text: str) -> str:
    """
    Xóa menu nav (>= 5 dòng * / + / -), cắt footer, xóa dòng rác.
    """
    if not text:
        return ""
    lines = text.splitlines()

    # Xóa block menu nav trong N dòng đầu
    i, limit = 0, min(25, len(lines))
    while i < limit:
        count, j = 0, i
        while j < len(lines):
            s = lines[j].strip()
            if _NAV_LINE.match(s):
                count += 1
                j += 1
            elif s == "" and j > i:
                j += 1
            else:
                break
        if count >= 5:
            lines = lines[:i] + lines[j:]
            break
        i += 1

    # Cắt footer - chỉ tìm trong 30% cuối file để tránh cắt nội dung hợp lệ
    cut = len(lines)
    footer_search_start = max(0, int(len(lines) * 0.7))
    for i in range(footer_search_start, len(lines)):
        if any(m in lines[i].strip() for m in FOOTER_MARKERS):
            cut = i
            break
    lines = lines[:cut]

    # Xóa dòng rác (strip cả bullet prefix trước khi so sánh)
    result = [l for l in lines if _strip_bullet(l).lower() not in JUNK_LINES]
    content = "\n".join(result).strip()
    return normalize_empty_lines(content)
