#!/usr/bin/env python3
"""
Xử lý: Metadata tags (category, year).
Trường hợp: Gắn nhãn diem_chuan, hoc_phi... để filter khi search.
"""
import re
from typing import Optional

YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")

METADATA_TAG_RULES = {
    "diem_chuan": ["điểm chuẩn", "điểm trúng tuyển", "điểm xét tuyển", "bảng điểm"],
    "hoc_phi": ["học phí", "mức học phí", "lệ phí"],
    "chi_tieu": ["chỉ tiêu tuyển sinh", "chỉ tiêu xét tuyển"],
    "nganh_hoc": ["mã ngành", "ngành đào tạo", "tổ hợp môn", "khối xét tuyển"],
    "xet_tuyen": ["xét tuyển", "phương thức xét tuyển", "nguyện vọng", "nhập học"],
    "hoc_bong": ["học bổng", "hỗ trợ tài chính"],
    "lich_tuyen_sinh": ["lịch tuyển sinh", "hạn nộp hồ sơ", "thời hạn đăng ký"],
    "gioi_thieu": ["sứ mạng", "tầm nhìn", "triết lý giáo dục"],
}


def detect_metadata_tags(text: str) -> list[str]:
    """Phát hiện tags: diem_chuan, hoc_phi, year..."""
    text_lower = text.lower()
    tags = []
    for tag, keywords in METADATA_TAG_RULES.items():
        if any(kw in text_lower for kw in keywords):
            tags.append(tag)
    for year in set(YEAR_PATTERN.findall(text)):
        if 2015 <= int(year) <= 2030:
            tags.append(year)
    return sorted(set(tags))


def detect_year(text: str) -> Optional[int]:
    """Lấy năm từ nội dung."""
    years = [int(m) for m in YEAR_PATTERN.findall(text) if 2015 <= int(m) <= 2030]
    return max(years) if years else None
