from database.connect import get_db


SCHEMA = {
    "_id": None,
    "content": None,      # Nội dung thuần (KHÔNG có [Title][URL]), dùng để embed + hiển thị
    "embedding": None,    # Vector 768 chiều
    "school": None,       # Mã trường (ptit, hust, ...)
    "year":None,
    "source_file": None,  # Tên file .md gốc
    "source_url": None,   # URL gốc crawl được
    "source_title": None, # Tiêu đề trang web
    "tags": None,         # Metadata: ["hoc_phi", "diem_chuan", "2024", ...]
    "chunk_id": None,     # Số thứ tự đoạn (chunk) trong file
    "total_chunks": None, # Tổng số chunk của file
}

COLLECTION_NAME = "documents"
VECTOR_INDEX_NAME = "vector_index"
_collection = None


def get_collection():
    """Trả về collection 'documents' (kết nối 1 lần duy nhất)."""
    global _collection
    if _collection is None:
        _collection = get_db()[COLLECTION_NAME]
    return _collection