"""
Chat Handler - Logic xử lý chat (tách khỏi router để dễ đọc)
Sử dụng lớp RAG theo thiết kế báo cáo (Hình 4.2.2).
"""
from services import rewrite_and_hyde, rerank_docs
import re
from services.rag import get_rag
from utils.session import session_manager
from utils.nomalize import check_intent


# Cụm từ câu hỏi thật: nếu có trong query → không phải chọn trường, vào RAG
QUESTION_PHRASES = (
    "điểm chuẩn", "diem chuan", "học phí", "hoc phi", "chỉ tiêu", "chi tieu",
    "ngành học", "nganh hoc", "xét tuyển", "xet tuyen", "học bổng", "hoc bong",
    "ký túc", "ky tuc", "túc xá", "tuc xa",
)

def is_school_selection(query: str) -> bool:
    """User chỉ nhập tên trường (chọn trường) hay câu hỏi thật?"""
    q = query.lower().strip().rstrip("!.,?")
    words = q.split()
    # Có cụm từ câu hỏi → câu hỏi thật, vào RAG (vd: "điểm chuẩn ptit")
    if any(phrase in q for phrase in QUESTION_PHRASES):
        return False
    if len(words) > 5:
        return False
    filler = {"truong", "trường", "dai", "đại", "hoc", "học", "mình", "minh", "toi", "tôi",
              "chon", "chọn", "la", "là", "muon", "muốn", "hoi", "hỏi", "ve", "về",
              "thong", "thông", "tin", "em"}
    from models.school import detect_school
    school = detect_school(query)
    if not school:
        return False
    remaining = [w for w in q.split() if w not in filler]
    return len(remaining) <= 3


def resolve_school(query: str, session_id: str) -> str | None:
    """Xác định trường đang focus từ query hoặc session."""
    from models.school import detect_school
    school = detect_school(query)
    if school:
        session_manager.set_school(session_id, school)
        return school
    return session_manager.get_school(session_id)


def _get_schools_list() -> str:
    """Format danh sách trường cho câu trả lời."""
    from models.school import get_all_schools
    schools = get_all_schools()
    return "\n".join([f"* **{s['name']}**" for s in schools])


def _get_school_name(school_id: str) -> str:
    """Lấy tên đầy đủ của trường."""
    from models.school import get_all_schools
    info = next((s for s in get_all_schools() if s["school_id"] == school_id), None)
    return info["name"] if info else school_id


def _detect_query_tags(query: str) -> list[str]:
    """Suy ra tags tu cau hoi (nam + loai thong tin) de loc search chinh xac hon."""
    q = (query or "").lower()
    tags = []

    # Chi lay tag hop le (khong gom nam)
    if "điểm chuẩn" in q or "diem chuan" in q or "điểm trúng tuyển" in q:
        tags.append("diem_chuan")
    if "ngành học" in q or "nganh hoc" in q:
        tags.append("nganh_hoc")
    if "xét tuyển" in q or "xet tuyen" in q:
        tags.append("xet_tuyen")
    if "điều kiện xét tuyển" in q or "dieu kien xet tuyen" in q:
        tags.append("dieu_kien_xet_tuyen")
    if "chỉ tiêu" in q or "chi tieu" in q:
        tags.append("chi_tieu")
    if "học phí" in q or "hoc phi" in q:
        tags.append("hoc_phi")
    if "học bổng" in q or "hoc bong" in q:
        tags.append("hoc_bong")
    if "cơ hội việc làm" in q or "co hoi viec lam" in q:
        tags.append("co_hoi_viec_lam")
    if "lịch tuyển sinh" in q or "lich tuyen sinh" in q:
        tags.append("lich_tuyen_sinh")
    if "thông tin" in q or "info" in q:
        tags.append("info")

    # Loai trung lap, giu thu tu on dinh
    deduped = []
    seen = set()
    for t in tags:
        if t and t not in seen:
            deduped.append(t)
            seen.add(t)
    return deduped


def _detect_query_year(query: str) -> str | None:
    """Lấy năm cụ thể trong câu hỏi (vd: 2025)."""
    q = (query or "").lower()
    match = re.search(r"\b20\d{2}\b", q)
    if not match:
        return None
    year_str = match.group(0)
    return int(year_str) if year_str.isdigit() else year_str


def handle_intent_nonsense(query: str, session_id: str) -> tuple[str, list]:
    """Xử lý câu vô nghĩa."""
    answer = "Xin lỗi, tôi không hiểu ý bạn. Bạn có thể đặt câu hỏi về tuyển sinh đại học không? 😊"
    session_manager.add_message(session_id, "user", query)
    session_manager.add_message(session_id, "bot", answer)
    return answer, []


def handle_intent_greeting(query: str, session_id: str) -> tuple[str, list]:
    """Xử lý chào hỏi."""
    lst = _get_schools_list()
    answer = f"Xin chào! Tôi là trợ lý tư vấn tuyển sinh.\n\n{lst}\n\nBạn muốn tìm hiểu về trường nào?"
    session_manager.add_message(session_id, "user", query)
    session_manager.add_message(session_id, "bot", answer)
    return answer, []


def handle_intent_confirm(query: str, session_id: str) -> tuple[str, list]:
    """Xử lý xác nhận (có, đúng, ok...)."""
    school = session_manager.get_school(session_id)
    if school:
        school_name = _get_school_name(school)
        answer = (
            f"Tuyệt! Bạn đang tìm hiểu về **{school_name}**.\n"
            "Bạn có thể hỏi về: điểm chuẩn, học phí, chỉ tiêu, ngành học, "
            "xét tuyển, học bổng, ký túc xá... Hãy hỏi bất kỳ điều gì nhé!"
        )
    else:
        lst = _get_schools_list()
        answer = f"Bạn muốn hỏi thông tin của trường nào?\n\n{lst}\n\nHãy cho tôi biết nhé!"
    session_manager.add_message(session_id, "user", query)
    session_manager.add_message(session_id, "bot", answer)
    return answer, []


def handle_school_selection(query: str, session_id: str, school: str) -> tuple[str, list]:
    """User chọn trường → xác nhận."""
    school_name = _get_school_name(school)
    answer = f"Bạn đã chọn **{school_name}**. Hãy hỏi bất kỳ câu hỏi nào về trường này nhé!"
    session_manager.add_message(session_id, "bot", answer)
    return answer, []


def handle_no_school(session_id: str) -> tuple[str, list]:
    """Chưa có trường → hỏi user chọn."""
    lst = _get_schools_list()
    answer = f"Bạn muốn hỏi thông tin của trường nào?\n\n{lst}\n\nHãy cho tôi biết nhé!"
    session_manager.add_message(session_id, "bot", answer)
    return answer, []


def handle_rag(query: str, session_id: str, school: str) -> tuple[str, list]:
    """Pipeline RAG: Rewrite → Search (RAG.retrieve) → Rerank → Generate (RAG.generate)."""
    rag = get_rag()
    school_name = _get_school_name(school)
    history = session_manager.get_history(session_id)

    # Rewrite + HyDE
    effective_query, hyde = rewrite_and_hyde(query, history, school_name=school_name)
    print(f"\n{'='*60}")
    _log_step("QUERY", query)
    _log_step("REFLECT", effective_query)
    _log_step("SCHOOL", f"{school} ({school_name})")

    # Keyword boost
    q_lower = effective_query.lower()
    if "điểm chuẩn" in q_lower or "diem chuan" in q_lower:
        effective_query += " điểm trúng tuyển bảng điểm chuẩn"
    if any(k in q_lower for k in ("các năm khác", "cac nam khac", "năm trước", "nam truoc", "năm khác", "nam khac", "cac nam truoc")):
        effective_query += " điểm trúng tuyển 2020 2021 2022 2023 2024 các năm trước"

    _log_step("HYDE", hyde[:120] + "...")

    # Tag filter tu query (nam + loai thong tin) de tang do chinh xac
    tags = _detect_query_tags(effective_query)
    if tags:
        print(f"[TAGS]     query tags={tags}")
    year = _detect_query_year(effective_query)
    if year:
        print(f"[YEAR]     query year={year}")

    # Vector search (RAG.retrieve): tăng limit cho câu hỏi điểm chuẩn (bảng nhiều ngành)
    search_limit = 18 if ("điểm chuẩn" in q_lower or "diem chuan" in q_lower) else 10
    context_docs = rag.retrieve(
        effective_query, hyde, school=school, tags=tags, year=year,
        num_candidates=300, limit=search_limit,
    )
    _log_search(context_docs)
    if not context_docs:
        answer = "Xin lỗi, tôi không tìm thấy thông tin liên quan. Bạn thử hỏi cách khác nhé!"
        session_manager.add_message(session_id, "bot", answer)
        return answer, []

    # Rerank (bo qua khi cau hoi diem chuan de giu du du lieu)
    if "điểm chuẩn" in q_lower or "diem chuan" in q_lower:
        print("[RERANK]   skipped for score-table query")
        low_confidence = False
    else:
        context_docs = rerank_docs(effective_query, context_docs)
        print(f"[RERANK]   kept: {len(context_docs)} chunks")
        max_rerank = max((d.get("rerank_score", 0) for d in context_docs), default=0)
        # Chỉ "I don't know" khi điểm <= 2 (ít/không liên quan). Điểm 3 = liên quan → vẫn trả lời
        low_confidence = max_rerank <= 2
        if low_confidence:
            print("[LLM] low_confidence=True (rerank scores thấp)")

    # Generate (RAG.generate)
    answer = rag.generate(query, context_docs, history=history, low_confidence=low_confidence)
    session_manager.add_message(session_id, "bot", answer)

    sources = [
        {"content": d["content"][:200], "score": round(d.get("score", 0), 4),
         "source_url": d.get("source_url", ""), "source_title": d.get("source_title", "")}
        for d in context_docs
    ]
    return answer, sources


def _log_step(label: str, value: str):
    print(f"[{label:8}] {value}")


def _log_search(docs: list):
    print(f"[SEARCH]   found: {len(docs)} chunks")
    for i, d in enumerate(docs):
        url = (d.get("source_url") or "")[-55:]
        year = d.get("year", "")
        print(
            f"           [{i+1}] score={d.get('score',0):.4f} tags={d.get('tags',[])} "
            f"year={year} url=...{url}"
        )
    print("=" * 60)
