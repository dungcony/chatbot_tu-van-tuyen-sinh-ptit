#!/usr/bin/env python3
"""
Xử lý: Từ viết tắt & đồng nghĩa.
Trường hợp: Người dùng hỏi "HSA" nhưng web ghi "Đánh giá năng lực ĐHQGHN".
"""
import re

# Từ viết tắt + keyword ngữ cảnh tuyển sinh để tránh false positive
SYNONYM_EXPANSIONS = [
    (r"\bHSA\b", "HSA (Đánh giá năng lực ĐHQGHN)"),
    (r"\bAPT\b", "APT (Đánh giá tư duy)"),
    (r"\bSAT\b", "SAT (Scholastic Assessment Test)"),
    (r"\bACT\b", "ACT (American College Testing)"),
    (r"\bTSA\b", "TSA (Đánh giá tư duy)"),
    (r"\bSPT\b", "SPT (Đánh giá năng lực)"),
]

# Chỉ expand khi nội dung có liên quan đến tuyển sinh / điểm
_CONTEXT_KEYWORDS = [
    "tuyển sinh", "xét tuyển", "điểm", "thang", "nguyện vọng",
    "đại học", "phương thức", "năng lực", "tư duy",
]


def _has_admission_context(text: str) -> bool:
    """Kiểm tra nội dung có ngữ cảnh tuyển sinh không."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in _CONTEXT_KEYWORDS)


def expand_synonyms(text: str) -> str:
    """
    Bổ sung giải thích từ viết tắt lần đầu gặp.
    Chỉ expand khi nội dung có ngữ cảnh tuyển sinh để tránh false positive.
    """
    if not _has_admission_context(text):
        return text
    result = text
    for pattern, expansion in SYNONYM_EXPANSIONS:
        if re.search(pattern, result, re.I) and expansion not in result:
            result = re.sub(pattern, expansion, result, count=1, flags=re.I)
    return result
