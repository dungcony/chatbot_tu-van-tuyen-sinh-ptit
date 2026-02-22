#!/usr/bin/env python3
"""
Tiện ích xử lý dữ liệu dạng ảnh trong quá trình crawl.
- Xử lý ảnh bảng điểm, ảnh thông báo, ảnh scan...
- OCR, trích xuất text, chuẩn hóa bảng từ ảnh
"""
from normalize.content_handlers import extract_text_image


def ocr_image_table(url: str) -> str:
    """OCR bảng điểm từ ảnh."""
    return extract_content(url, "image")[0]


def get_image_metadata(url: str) -> dict:
    """Trích xuất metadata ảnh."""
    meta = extract_metadata_video(url)
    meta["type"] = "image"
    return meta
