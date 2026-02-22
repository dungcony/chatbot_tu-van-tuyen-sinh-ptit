"""
Vector Search - Tim kiem ngu nghia trong MongoDB
Ho tro loc theo truong (school) va tags.
Dual search: ket hop ket qua tu nhieu query de tang do phu (recall).
"""
from models.document import get_collection, VECTOR_INDEX_NAME
from services.embedding import get_embedding_model
from rapidfuzz import process, fuzz


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
    "điện tử viễn thông": "điện tử viễn thông",
    "dtvt": "điện tử viễn thông",
    "truyền thông đa phương tiện": "đa phương tiện",
    "multimedia": "đa phương tiện",
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

# Danh sách tên ngành CHÍNH XÁC để fuzzy match
PROGRAM_NAMES = list(set(PROGRAM_KEYWORDS.values()))


import re

def _detect_program_name(query: str) -> str:
    """Detect ten nganh cu the tu cau hoi (fuzzy + word boundary cho keyword ngắn)."""
    q_lower = query.lower()
    # Trước tiên thử match cứng
    for keyword, program in PROGRAM_KEYWORDS.items():
        # Nếu keyword ngắn (<=3 ký tự), kiểm tra word boundary
        if len(keyword) <= 3:
            if re.search(rf'\b{re.escape(keyword)}\b', q_lower):
                return program
        else:
            if keyword in q_lower:
                return program
    # Nếu không match cứng, dùng fuzzy
    result = process.extractOne(q_lower, PROGRAM_NAMES, scorer=fuzz.partial_ratio)
    if result and result[1] >= 70:
        return result[0]
    return ""


def _text_search_score_docs(school: str, program_name: str, tags: list | None = None, limit: int = 5) -> list:
    """
    Text search: tim docs chua ten nganh CU THE trong content.
    Dac biet huu ich cho du lieu dang bang (table) ma vector search miss.
    """
    collection = get_collection()
    # DB có thể lưu "ptit" hoặc "ptit/" → match cả hai
    s_norm = _normalize_school(school)
    query_filter = {"school": {"$in": [s_norm, s_norm + "/"]}}
    if tags:
        query_filter["tags"] = {"$in": tags}

    # Tim docs co chua ten nganh trong content (case-insensitive regex)
    query_filter["content"] = {"$regex": program_name, "$options": "i"}

    results = list(collection.find(
        query_filter,
        {"_id": 0, "content": 1, "school": 1, "tags": 1,
         "source_url": 1, "source_title": 1, "source_file": 1,
         "source_date": 1, "questions": 1}
    ).limit(limit))

    # Gan score gia (0.80) de ket qua text search hoa nhap duoc voi vector results
    # Danh dau _text_match=True de reranker khong drop nhung doc nay
    for doc in results:
        doc["score"] = 0.80
        doc["_text_match"] = True
    return results


def _normalize_school(s: str) -> str:
    """Chuẩn hóa school: ptit, ptit/ → cùng format (bỏ trailing /)."""
    return (s or "").strip().rstrip("/") or ""


def _school_matches(doc_school: str, query_school: str) -> bool:
    """So sánh school: ptit vs ptit/ đều match."""
    return _normalize_school(doc_school) == _normalize_school(query_school)


def _single_vector_search(query_vector, school=None, tags=None,
                           num_candidates=200, limit=6, score_threshold=0.65):
    """Thuc hien 1 lan vector search voi optional tag filter."""
    from pymongo.errors import OperationFailure

    collection = get_collection()

    # Build filter (school, tags phải có trong index definition - Atlas Vector Search)
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
            "limit": limit
        }
    }
    if vs_filter:
        vs_stage["$vectorSearch"]["filter"] = vs_filter

    pipeline = [
        vs_stage,
        {"$project": {
            "_id": 0, "content": 1, "school": 1, "tags": 1,
            "source_url": 1, "source_title": 1, "source_file": 1,
            "source_date": 1, "questions": 1,
            "score": {"$meta": "vectorSearchScore"}
        }}
    ]

    try:
        results = list(collection.aggregate(pipeline))
    except OperationFailure as e:
        # Index chưa có filter fields (school, tags) → search không filter, lọc sau
        if "needs to be indexed as filter" in str(e):
            print(f"[VECTOR-SEARCH] Filter không hỗ trợ, fallback: search không filter + lọc Python")
            vs_stage["$vectorSearch"].pop("filter", None)
            vs_stage["$vectorSearch"]["limit"] = limit * 5  # Lấy nhiều để lọc
            results = list(collection.aggregate(pipeline))
            if school:
                results = [d for d in results if _school_matches(d.get("school", ""), school)]
            if tags:
                results = [d for d in results if d.get("tags") and set(d["tags"]) & set(tags)]
            results = results[:limit]
        else:
            raise

    return [doc for doc in results if doc.get("score", 0) >= score_threshold]


def _merge_results(priority_results: list, other_result_lists: list, max_results: int = 10) -> list:
    """
    Merge ket qua search: uu tien tag-filtered results (chinh xac nhat),
    sau do bo sung tu cac nguon khac bang round-robin.
    """
    seen_keys = set()
    merged = []

    def _add_doc(doc):
        key = doc["content"][:200]
        if key not in seen_keys:
            seen_keys.add(key)
            merged.append(doc)
            return True
        return False

    # 1) Uu tien: lay toi da (max_results // 2) tu tag-filtered results
    tag_limit = max(max_results // 2, 3)
    for doc in priority_results[:tag_limit]:
        _add_doc(doc)
        if len(merged) >= max_results:
            return merged

    # 2) Bo sung: round-robin tu cac nguon khac (orig + hyde)
    if other_result_lists:
        max_len = max(len(r) for r in other_result_lists)
        for idx in range(max_len):
            for results in other_result_lists:
                if idx < len(results):
                    _add_doc(results[idx])
                    if len(merged) >= max_results:
                        return merged
    return merged


def vector_search(query, school=None, num_candidates=200, limit=6, score_threshold=0.55):
    """Vector search co ban (backward compatible)."""
    embedding_model = get_embedding_model()
    query_vector = embedding_model.embed_query(query)
    return _single_vector_search(query_vector, school=school,
                                  num_candidates=num_candidates, limit=limit,
                                  score_threshold=score_threshold)


def dual_vector_search(original_query, hyde_query, school=None,
                        num_candidates=200, limit=10, score_threshold=0.55):
    """
    Dual search: tim kiem voi CA 2 query (original + HyDE), merge ket qua.

    Ly do: HyDE sinh van ban gia dinh giup match ngu canh,
    nhung doi khi lech khoi cau hoi goc (dac biet voi bang diem).
    Search bang query goc dam bao khong bo sot ket qua truc tiep.

    Khong dung tag-filter: cau hoi user kho map chinh xac tag,
    vector search semantic da du de tim doc lien quan.
    """
    embedding_model = get_embedding_model()

    # Search 1: query goc
    orig_vector = embedding_model.embed_query(original_query)
    results_orig = _single_vector_search(
        orig_vector, school=school,
        num_candidates=num_candidates, limit=limit,
        score_threshold=score_threshold
    )

    # Search 2: HyDE query
    hyde_vector = embedding_model.embed_query(hyde_query)
    results_hyde = _single_vector_search(
        hyde_vector, school=school,
        num_candidates=num_candidates, limit=limit,
        score_threshold=score_threshold
    )

    # Text search: tim bang diem theo ten nganh (vd: "CNTT") - khong can tag
    program_name = _detect_program_name(original_query)
    text_results = []
    if program_name and school:
        try:
            text_results = _text_search_score_docs(school, program_name, tags=None, limit=5)
            if text_results:
                print(f"[DUAL-SEARCH] text-search ({program_name}): {len(text_results)} results")
        except Exception as e:
            print(f"[DUAL-SEARCH] text-search failed: {e}")

    merged = _merge_results(text_results, [results_orig, results_hyde], max_results=limit)
    print(f"[DUAL-SEARCH] merged total    : {len(merged)} results")

    # Boost: docs có questions khớp với query -> đẩy lên đầu (tăng độ chính xác)
    merged = _boost_by_questions_match(merged, original_query)
    return merged


# Map tag -> tên loại tài liệu (cho metadata injection)
TAG_TO_DOC_TYPE = {
    "diem_chuan": "Điểm chuẩn",
    "hoc_phi": "Học phí",
    "chi_tieu": "Chỉ tiêu",
    "nganh_hoc": "Ngành học",
    "xet_tuyen": "Xét tuyển",
    "hoc_bong": "Học bổng",
    "ky_tuc_xa": "Ký túc xá",
}


def _extract_year_from_doc(doc: dict) -> str:
    """Trích năm từ source_date hoặc tags (vd: 2024, 2023)."""
    if doc.get("source_date"):
        s = str(doc["source_date"])
        year_match = re.search(r"\b(20\d{2})\b", s)
        if year_match:
            return year_match.group(1)
    tags = doc.get("tags") or []
    for t in tags:
        if re.match(r"^20\d{2}$", str(t)):
            return str(t)
    return ""


def _get_doc_type(doc: dict) -> str:
    """Lấy loại tài liệu từ tags."""
    tags = doc.get("tags") or []
    for t in tags:
        if t in TAG_TO_DOC_TYPE:
            return TAG_TO_DOC_TYPE[t]
    return "Thông tin chung"


def _boost_by_questions_match(docs: list, query: str) -> list:
    """
    Nếu doc có trường questions và query khớp với câu hỏi mẫu -> đẩy lên đầu.
    Dùng fuzzy match để tăng recall.
    """
    if not docs or not query:
        return docs
    q_lower = query.lower()
    boosted, rest = [], []
    for doc in docs:
        questions = doc.get("questions")
        if not questions:
            rest.append(doc)
            continue
        qlist = questions if isinstance(questions, list) else [questions]
        matched = False
        for q in qlist:
            if q is not None and str(q).strip() and len(str(q)) >= 5:
                qstr = str(q).lower()
                if qstr in q_lower or q_lower in qstr:
                    matched = True
                    break
                if process.extractOne(q_lower, [qstr], scorer=fuzz.partial_ratio)[1] >= 75:
                    matched = True
                    break
        if matched:
            boosted.append(doc)
        else:
            rest.append(doc)
    result = boosted + rest
    if boosted:
        print(f"[DUAL-SEARCH] questions-match boost: {len(boosted)} docs")
    return result


def enrich_context_docs(docs: list, sort_by_recency: bool = True) -> list:
    """
    Context Enrichment: Chuẩn bị docs cho LLM với metadata injection.
    - Thêm [Thời gian: X] [Loại: Y] vào mỗi chunk
    - Sắp xếp theo source_date (mới nhất trước) khi có mâu thuẫn
    - Trả về docs đã được enrich (thêm _enriched_content cho LLM)
    """
    if not docs:
        return docs

    for doc in docs:
        year = _extract_year_from_doc(doc)
        doc_type = _get_doc_type(doc)
        meta_parts = []
        if year:
            meta_parts.append(f"[Thời gian: {year}]")
        meta_parts.append(f"[Loại: {doc_type}]")
        doc["_enriched_content"] = " ".join(meta_parts) + f" [Nội dung: {doc['content']}]"
        # Giữ content gốc để backward compat
        doc["_year"] = year
        doc["_doc_type"] = doc_type

    if sort_by_recency:
        def _sort_key(d):
            year = d.get("_year") or ""
            date = d.get("source_date") or ""
            return (year, date)

        docs.sort(key=_sort_key, reverse=True)

    return docs
