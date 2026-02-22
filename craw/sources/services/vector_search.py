"""
Vector Search - Tìm kiếm ngữ nghĩa trong MongoDB
Hỗ trợ lọc theo trường (school) và tags.
Dual search: kết hợp kết quả từ nhiều query để tăng độ phủ (recall).
"""
import logging
from sources.models.document import get_collection, VECTOR_INDEX_NAME
from sources.services.embed_service import get_embedder

logger = logging.getLogger(__name__)

# Map: keyword câu hỏi -> tên ngành CHÍNH XÁC trong data để text search
PROGRAM_KEYWORDS = {
    "cntt": "Công nghệ thông tin",
    "công nghệ thông tin": "Công nghệ thông tin",
    "an toàn thông tin": "An toàn thông tin",
    "attt": "An toàn thông tin",
    "khoa học máy tính": "Khoa học máy tính",
    "kỹ thuật phần mềm": "Kỹ thuật phần mềm",
    "ktpm": "Kỹ thuật phần mềm",
    "marketing": "Marketing",
    "thương mại điện tử": "Thương mại điện tử",
    "tmdt": "Thương mại điện tử",
    "điện tử viễn thông": "Điện tử viễn thông",
    "dtvt": "Điện tử viễn thông",
    "truyền thông đa phương tiện": "Đa phương tiện",
    "multimedia": "Đa phương tiện",
    "kế toán": "Kế toán",
    "quản trị kinh doanh": "Quản trị kinh doanh",
    "qtkd": "Quản trị kinh doanh",
    "khoa học dữ liệu": "Khoa học dữ liệu",
    "data science": "Khoa học dữ liệu",
    "quan hệ công chúng": "Quan hệ công chúng",
    "pr": "Quan hệ công chúng",
    "báo chí": "Báo chí",
    "iot": "Internet vạn vật",
    "trí tuệ nhân tạo": "Trí tuệ nhân tạo",
    "ai": "Trí tuệ nhân tạo",
}

# Map: keyword trong câu hỏi -> tags liên quan trong DB
QUERY_TAG_MAP = {
    "điểm chuẩn": ["diem_chuan"],
    "diem chuan": ["diem_chuan"],
    "điểm trúng tuyển": ["diem_chuan"],
    "diem trung tuyen": ["diem_chuan"],
    "học phí": ["hoc_phi"],
    "hoc phi": ["hoc_phi"],
    "chỉ tiêu": ["chi_tieu"],
    "chi tieu": ["chi_tieu"],
    "ngành": ["nganh_hoc"],
    "nganh": ["nganh_hoc"],
    "mã ngành": ["nganh_hoc"],
    "ma nganh": ["nganh_hoc"],
    "xét tuyển": ["xet_tuyen"],
    "xet tuyen": ["xet_tuyen"],
    "học bổng": ["hoc_bong"],
    "hoc bong": ["hoc_bong"],
    "ký túc xá": ["ky_tuc_xa"],
    "ky tuc xa": ["ky_tuc_xa"],
    "lịch tuyển sinh": ["lich_tuyen_sinh"],
    "lich tuyen sinh": ["lich_tuyen_sinh"],
}


def _detect_program_name(query: str) -> str:
    """Phát hiện tên ngành cụ thể từ câu hỏi."""
    q_lower = query.lower()
    for keyword, program in PROGRAM_KEYWORDS.items():
        if keyword in q_lower:
            return program
    return ""


def detect_query_tags(query: str) -> list:
    """Phát hiện tags liên quan từ câu hỏi của user."""
    q_lower = query.lower()
    tags = set()
    for keyword, tag_list in QUERY_TAG_MAP.items():
        if keyword in q_lower:
            tags.update(tag_list)
    return list(tags)


def _embed_query(text: str) -> list[float]:
    """Embed 1 câu query thành vector."""
    model = get_embedder()
    vector = model.encode(text)
    if hasattr(vector, "tolist"):
        return vector.tolist()
    return list(vector)


def _text_search_score_docs(
    school: str | None,
    program_name: str,
    tags: list,
    limit: int = 5,
) -> list[dict]:
    """
    Text search: tìm docs chứa tên ngành CỤ THỂ trong content.
    Đặc biệt hữu ích cho dữ liệu dạng bảng (table) mà vector search miss.
    """
    collection = get_collection()
    query_filter = {"content": {"$regex": program_name, "$options": "i"}}
    if school:
        query_filter["school"] = school
    if tags:
        query_filter["tags"] = {"$in": tags}

    results = list(
        collection.find(
            query_filter,
            {
                "_id": 0,
                "content": 1,
                "school": 1,
                "tags": 1,
                "source_url": 1,
                "source_title": 1,
                "source_file": 1,
            },
        ).limit(limit)
    )

    for doc in results:
        doc["score"] = 0.80
        doc["_text_match"] = True
    return results


def _single_vector_search(
    query_vector: list[float],
    school: str | None = None,
    tags: list | None = None,
    num_candidates: int = 200,
    limit: int = 6,
    score_threshold: float = 0.55,
) -> list[dict]:
    """Thực hiện 1 lần vector search với optional filter."""
    collection = get_collection()

    vs_filter = {}
    if school:
        vs_filter["school"] = school
    if tags:
        vs_filter["tags"] = {"$in": tags}

    vs_stage = {
        "$vectorSearch": {
            "index": VECTOR_INDEX_NAME,
            "path": "embedding",
            "queryVector": query_vector,
            "numCandidates": num_candidates,
            "limit": limit,
        }
    }
    if vs_filter:
        vs_stage["$vectorSearch"]["filter"] = vs_filter

    pipeline = [
        vs_stage,
        {
            "$project": {
                "_id": 0,
                "content": 1,
                "school": 1,
                "tags": 1,
                "source_url": 1,
                "source_title": 1,
                "source_file": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    results = list(collection.aggregate(pipeline))
    return [doc for doc in results if doc.get("score", 0) >= score_threshold]


def _merge_results(
    priority_results: list[dict],
    other_result_lists: list[list[dict]],
    max_results: int = 10,
) -> list[dict]:
    """
    Merge kết quả: ưu tiên tag-filtered results, sau đó bổ sung từ các nguồn khác (round-robin).
    """
    seen_keys = set()
    merged = []

    def _add_doc(doc: dict) -> bool:
        key = (doc.get("content") or "")[:200]
        if key not in seen_keys:
            seen_keys.add(key)
            merged.append(doc)
            return True
        return False

    tag_limit = max(max_results // 2, 3)
    for doc in priority_results[:tag_limit]:
        _add_doc(doc)
        if len(merged) >= max_results:
            return merged

    if other_result_lists:
        max_len = max(len(r) for r in other_result_lists)
        for idx in range(max_len):
            for results in other_result_lists:
                if idx < len(results):
                    _add_doc(results[idx])
                    if len(merged) >= max_results:
                        return merged
    return merged


def vector_search(
    query: str,
    school: str | None = None,
    num_candidates: int = 200,
    limit: int = 6,
    score_threshold: float = 0.55,
) -> list[dict]:
    """Vector search cơ bản (backward compatible)."""
    query_vector = _embed_query(query)
    return _single_vector_search(
        query_vector,
        school=school,
        num_candidates=num_candidates,
        limit=limit,
        score_threshold=score_threshold,
    )


def dual_vector_search(
    original_query: str,
    hyde_query: str,
    school: str | None = None,
    num_candidates: int = 200,
    limit: int = 10,
    score_threshold: float = 0.55,
) -> list[dict]:
    """
    Dual search: tìm kiếm với CẢ 2 query (original + HyDE), merge kết quả.
    Thêm tag-aware search nếu detect được tags từ câu hỏi.
    """
    query_tags = detect_query_tags(original_query)

    # Search 1: query gốc
    orig_vector = _embed_query(original_query)
    results_orig = _single_vector_search(
        orig_vector,
        school=school,
        num_candidates=num_candidates,
        limit=limit,
        score_threshold=score_threshold,
    )
    logger.debug("[DUAL-SEARCH] original query: %d results", len(results_orig))

    # Search 2: HyDE query
    hyde_vector = _embed_query(hyde_query)
    results_hyde = _single_vector_search(
        hyde_vector,
        school=school,
        num_candidates=num_candidates,
        limit=limit,
        score_threshold=score_threshold,
    )
    logger.debug("[DUAL-SEARCH] hyde query: %d results", len(results_hyde))

    all_results = [results_orig, results_hyde]
    tag_results = []

    # Search 3: tag-filtered (nếu có tags)
    if query_tags:
        try:
            tag_results = _single_vector_search(
                orig_vector,
                school=school,
                tags=query_tags,
                num_candidates=num_candidates,
                limit=limit,
                score_threshold=0.45,
            )
            logger.debug("[DUAL-SEARCH] tag-filtered %s: %d results", query_tags, len(tag_results))
        except Exception as e:
            logger.warning("[DUAL-SEARCH] tag-filter failed: %s", e)

    # Text search cho ngành cụ thể (bảng điểm, v.v.)
    program_name = _detect_program_name(original_query)
    if program_name and query_tags:
        try:
            specific_tags = [
                t for t in query_tags
                if t in ("diem_chuan", "hoc_phi", "chi_tieu")
            ]
            if not specific_tags:
                specific_tags = query_tags[:1]
            text_results = _text_search_score_docs(
                school, program_name, specific_tags, limit=5
            )
            if text_results:
                tag_results = text_results + tag_results
                logger.debug(
                    "[DUAL-SEARCH] text-search (%s, %s): %d results",
                    program_name, specific_tags, len(text_results),
                )
        except Exception as e:
            logger.warning("[DUAL-SEARCH] text-search failed: %s", e)

    merged = _merge_results(tag_results, all_results, max_results=limit)
    logger.debug("[DUAL-SEARCH] merged total: %d results", len(merged))
    return merged
