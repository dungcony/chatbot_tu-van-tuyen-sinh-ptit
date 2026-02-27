#!/usr/bin/env python3
"""
Tiện ích xử lý dữ liệu dạng file (PDF, DOCX, XLSX, JSON...) trong quá trình crawl.
- Trích xuất text từ file, chuẩn hóa nội dung
"""
from services.normalize.content_handlers import extract_text_pdf, extract_text_docx, extract_text_xlsx
import json


def extract_pdf(url: str) -> str:
    """Trích xuất text từ PDF qua URL."""
    return extract_text_pdf(url)


def extract_docx(url: str) -> str:
    """Trích xuất text từ DOCX qua URL."""
    return extract_text_docx(url)


def extract_xlsx(url: str) -> str:
    """Trích xuất text từ XLSX qua URL."""
    return extract_text_xlsx(url)


def extract_json(url: str) -> dict:
    """Tải và parse file JSON từ URL."""
    import requests
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

# Có thể bổ sung thêm các hàm xử lý file khác nếu cần
