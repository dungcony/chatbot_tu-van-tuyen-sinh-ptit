#!/usr/bin/env python3
"""
Tiện ích xử lý dữ liệu trong quá trình crawl.
- Xử lý từng file hoặc từng link khi crawl
- Có thể gọi từng chức năng: clean_html, remove_junk, extract_meta, ...
- Dùng cho scripts crawl để chuẩn hóa dữ liệu trước khi lưu
"""
import re
import html
from normalize import norm_meta, norm_clean_content, norm_clean_html, norm_tables


def clean_html(text: str) -> str:
    """Xóa thẻ HTML, decode entity, chuẩn hóa khoảng trắng."""
    return norm_clean_html.clean_html_and_special_chars(text)


def remove_junk(text: str) -> str:
    """Xóa menu nav, footer, dòng rác."""
    return norm_clean_content.clean_content(text)


def extract_meta(text: str, filename: str) -> tuple[str, str, str, str]:
    """Tách [Title][URL] và school."""
    content, url, title = norm_meta.extract_meta_header(text)
    school = norm_meta.extract_school(filename)
    return content, url, title, school


def normalize_table(text: str) -> str:
    """Chuyển bảng Markdown thành mô tả ngữ nghĩa."""
    return norm_tables.process_tables(text)


# Có thể bổ sung thêm các hàm xử lý khác nếu cần
