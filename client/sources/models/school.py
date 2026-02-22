"""
School Model - Phát hiện trường và danh sách trường hỗ trợ.
Dùng cho chatbot tư vấn tuyển sinh.
"""
import re

# Danh sách trường: (school_id, tên đầy đủ, từ khóa để detect)
# school_id phải khớp với trường "school" trong MongoDB documents
SCHOOLS = [
    {
        "school_id": "ptit",
        "name": "Học viện Công nghệ Bưu chính Viễn thông",
        "keywords": ["ptit", "bưu chính", "buu chinh", "viễn thông", "vien thong", "học viện ptit"],
    },
    {
        "school_id": "hust",
        "name": "Đại học Bách Khoa Hà Nội",
        "keywords": ["bách khoa", "bach khoa", "hust", "bkh", "đại học bách khoa", "dai hoc bach khoa"],
    },
    {
        "school_id": "uet",
        "name": "Đại học Công nghệ - ĐHQGHN",
        "keywords": ["uet", "đại học công nghệ", "dai hoc cong nghe", "đhqghn", "dhqghn"],
    },
    {
        "school_id": "neu",
        "name": "Đại học Kinh tế Quốc dân",
        "keywords": ["neu", "kinh tế quốc dân", "kinh te quoc dan", "đại học kinh tế", "dai hoc kinh te"],
    },
    {
        "school_id": "ftu",
        "name": "Đại học Ngoại thương",
        "keywords": ["ftu", "ngoại thương", "ngoai thuong", "đại học ngoại thương", "dai hoc ngoai thuong"],
    },
    {
        "school_id": "hcmut",
        "name": "Đại học Bách Khoa TP.HCM",
        "keywords": ["bách khoa tp hcm", "bach khoa tphcm", "hcmut", "bách khoa sài gòn", "bach khoa sai gon"],
    },
    {
        "school_id": "hcmus",
        "name": "Đại học Khoa học Tự nhiên TP.HCM",
        "keywords": ["khtn", "khoa học tự nhiên", "khoa hoc tu nhien", "hcmus", "đại học khoa học tự nhiên"],
    },
    {
        "school_id": "hou",
        "name": "Đại học Mở TP.HCM",
        "keywords": ["đại học mở", "dai hoc mo", "hou", "uni mở"],
    },
]


def _normalize(s: str) -> str:
    """Chuẩn hóa để so sánh (bỏ dấu, lowercase)."""
    s = s.lower().strip()
    s = re.sub(r"[àáạảãâầấậẩẫăằắặẳẵ]", "a", s)
    s = re.sub(r"[èéẹẻẽêềếệểễ]", "e", s)
    s = re.sub(r"[ìíịỉĩ]", "i", s)
    s = re.sub(r"[òóọỏõôồốộổỗơờớợởỡ]", "o", s)
    s = re.sub(r"[ùúụủũưừứựửữ]", "u", s)
    s = re.sub(r"[ỳýỵỷỹ]", "y", s)
    s = re.sub(r"[đ]", "d", s)
    return s


def detect_school(query: str) -> str | None:
    """
    Phát hiện trường từ câu hỏi của user.
    Trả về school_id nếu tìm thấy, None nếu không.
    """
    query_norm = _normalize(query)
    words = set(query_norm.split())

    # Ưu tiên match chính xác keyword
    for school in SCHOOLS:
        for kw in school["keywords"]:
            kw_norm = _normalize(kw)
            if kw_norm in query_norm or kw_norm in words:
                return school["school_id"]

    # Match từng từ
    for school in SCHOOLS:
        for kw in school["keywords"]:
            kw_words = set(_normalize(kw).split())
            if kw_words & words:  # có overlap
                return school["school_id"]

    return None


def get_all_schools() -> list[dict]:
    """
    Trả về danh sách tất cả trường hỗ trợ.
    Format: [{"school_id": "...", "name": "..."}, ...]
    """
    # Loại bỏ duplicate school_id (vd: hcmut có 2 entry)
    seen = set()
    result = []
    for s in SCHOOLS:
        if s["school_id"] not in seen:
            seen.add(s["school_id"])
            result.append({"school_id": s["school_id"], "name": s["name"]})
    return result
