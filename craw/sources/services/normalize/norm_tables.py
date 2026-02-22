from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
def process_tables(text: str) -> str:
    """
    Chuyển tất cả bảng Markdown trong text thành dạng mô tả ngữ nghĩa.
    """
    return normalize_tables_in_content(text)

#!/usr/bin/env python3
"""
Chuẩn hóa bảng biểu: chuyển bảng Markdown thành mô tả ngữ nghĩa (semantic text).
Dùng cho embedding, giúp model hiểu rõ thông tin bảng.
"""
import re

def md_table_to_text(md_table: str) -> str:
    """
    Chuyển bảng Markdown thành mô tả ngữ nghĩa.
    - Dòng header: xác định các trường.
    - Dòng dữ liệu: chuyển thành câu mô tả.
    """
    lines = [l.strip() for l in md_table.splitlines() if l.strip()]
    if not lines or not any('|' in l for l in lines):
        return md_table
    # Loại bỏ dòng phân cách ---
    header = None
    rows = []
    for line in lines:
        if re.match(r'^\|?\s*-{2,}', line):
            continue
        if header is None:
            header = [h.strip() for h in line.strip('|').split('|')]
        else:
            row = [c.strip() for c in line.strip('|').split('|')]
            if len(row) == len(header):
                rows.append(row)
    # Chuyển từng dòng thành câu mô tả
    sentences = []
    for row in rows:
        pairs = [f"{h}: {v}" for h, v in zip(header, row)]
        sentences.append(", ".join(pairs))
    return "\n".join(sentences)

def normalize_tables_in_content(text: str) -> str:
    """
    Tìm tất cả bảng Markdown trong text và chuyển thành mô tả ngữ nghĩa.
    """
    # Regex tìm bảng Markdown
    table_pattern = re.compile(r'(\n\s*\|[^\n]+\n(?:\s*\|[^\n]+\n)+)', re.MULTILINE)
    def replacer(match):
        md_table = match.group(0)
        return "\n" + md_table_to_text(md_table) + "\n"
    return table_pattern.sub(replacer, text)

def process_tables(text: str) -> str:
    """
    Chuyển tất cả bảng Markdown trong text thành dạng mô tả ngữ nghĩa.
    """
    return normalize_tables_in_content(text)
