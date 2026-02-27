#!/usr/bin/env python3
"""
Tiện ích xử lý video crawl.
- Trích xuất metadata video
"""
from services.normalize.content_handlers import extract_metadata_video


def get_video_metadata(url: str) -> dict:
    """Trích xuất metadata video từ URL."""
    return extract_metadata_video(url)
