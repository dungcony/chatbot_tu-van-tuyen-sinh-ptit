"""
LLM Service - Google Gemini
Tổng hợp thông tin từ context và sinh câu trả lời cho người dùng.
Sử dụng Google Gemini API cho response thông minh hơn.

Cải tiến:
  - System Instructions: Vai diễn + quy tắc cố định, giảm token mỗi lượt
  - Few-shot Prompting: Ví dụ trả lời đúng kèm trích dẫn
  - Chain-of-Thought: Suy nghĩ theo bước trước khi trả lời
  - I don't know: Không bịa khi dữ liệu không đủ
  - Xử lý mâu thuẫn: Ưu tiên tài liệu có ngày mới nhất

Tương lai: Context Caching (Gemini API) - cache context dài cho các chủ đề lặp lại
để giảm chi phí và tăng tốc. Cần migrate sang google-genai SDK.
"""

import re
from config import LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

# ── Provider hiện tại (đọc từ .env) ──────────────────────────────────
_PROVIDER = (LLM_PROVIDER or "gemini").lower().strip()
print(f"[LLM] Provider: {_PROVIDER}")

# ── Lazy-init clients ─────────────────────────────────────────────────
_openai_client = None
_gemini_model = None
_gemini_chat_model = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(
            api_key=LLM_API_KEY or "ollama",
            base_url=LLM_BASE_URL or "http://localhost:11434/v1",
        )
        print(f"[LLM] OpenAI-compat client: base_url={LLM_BASE_URL}, model={LLM_MODEL}")
    return _openai_client


def _get_gemini_model(system_instruction: str = ""):
    """Trả về Gemini GenerativeModel. Nếu có system_instruction thì tạo chat model."""
    global _gemini_model, _gemini_chat_model
    import google.generativeai as genai
    _gemini_model_name = LLM_MODEL or "gemini-2.0-flash-lite"
    genai.configure(api_key=LLM_API_KEY)
    if system_instruction:
        if _gemini_chat_model is None:
            _gemini_chat_model = genai.GenerativeModel(
                _gemini_model_name, system_instruction=system_instruction
            )
            print(f"[LLM] Gemini chat model: {_gemini_model_name}")
        return _gemini_chat_model
    else:
        if _gemini_model is None:
            _gemini_model = genai.GenerativeModel(_gemini_model_name)
            print(f"[LLM] Gemini model: {_gemini_model_name}")
        return _gemini_model


def _call_llm(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.1) -> str:
    """
    Unified LLM call — tự động chọn provider từ LLM_PROVIDER trong .env.
    Đổi provider chỉ cần sửa .env, không sửa code.
    """
    if _PROVIDER == "gemini":
        model = _get_gemini_model(system_instruction=system)
        prompt = user
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        try:
            return response.text.strip() if response.text else ""
        except ValueError:
            return ""
    else:
        # Groq / Ollama / OpenAI — tất cả đều dùng OpenAI SDK
        client = _get_openai_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        model_name = LLM_MODEL or ("llama-3.3-70b-versatile" if _PROVIDER == "groq" else "llama3.2")
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()


# ── Healthcheck LLM ──────────────────────────────────────────────────
def check_llm_connection() -> tuple[bool, str]:
    """
    Kiểm tra kết nối tới LLM (Gemini / Groq / Ollama / OpenAI-compat).
    - Trả về (ok: bool, message: str)
    - Chỉ gọi 1 prompt rất ngắn ("ping") để không tốn nhiều quota.
    """
    try:
        if _PROVIDER == "gemini":
            model = _get_gemini_model()
            response = model.generate_content(
                "ping",
                generation_config={"temperature": 0.0, "max_output_tokens": 1},
            )
            _ = _safe_response_text(response)
        else:
            client = _get_openai_client()
            model_name = LLM_MODEL or ("llama-3.3-70b-versatile" if _PROVIDER == "groq" else "llama3.2")
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "ping"}],
                temperature=0,
                max_tokens=1,
            )
            _ = resp.choices[0].message.content if resp.choices else ""

        print(f"[LLM] Healthcheck OK (provider={_PROVIDER})")
        return True, "OK"
    except Exception as e:
        print(f"[LLM] Healthcheck FAILED (provider={_PROVIDER}): {e}")
        return False, str(e)


# ── Giữ lại để không break code cũ nếu có nơi gọi trực tiếp ─────────
def _get_model():
    return _get_gemini_model()


def _get_chat_model():
    return _get_gemini_model(system_instruction=SYSTEM_INSTRUCTION)


def _safe_response_text(response) -> str:
    try:
        return response.text.strip() if response.text else ""
    except ValueError as e:
        print(f"[LLM] response.text failed: {e}")
        return ""


def _call_gemini(prompt: str, max_tokens: int = 1024) -> str:
    """Legacy wrapper — dùng _call_llm thay thế."""
    return _call_llm("", prompt, max_tokens=max_tokens)


SYSTEM_INSTRUCTION = """Bạn là trợ lý tư vấn tuyển sinh đại học. Nhiệm vụ: trả lời câu hỏi dựa CHÍNH XÁC trên thông tin tham khảo.

QUY TẮC BẮT BUỘC:
1. CHỈ trả lời dựa trên dữ liệu trong THÔNG TIN THAM KHẢO. TUYỆT ĐỐI không bịa, không suy đoán.
2. Khi trích dẫn số liệu (điểm chuẩn, chỉ tiêu, học phí...), ghi chính xác như dữ liệu.
3. Trả lời bằng tiếng Việt, ngắn gọn, rõ ràng. Cuối câu trả lời ghi nguồn theo format [Nguồn X].
4. XỬ LÝ MÂU THUẪN: Nếu 2 đoạn đưa ra con số khác nhau (vd: thông báo cũ vs mới), ƯU TIÊN đoạn có [Thời gian: năm] hoặc ngày tháng GẦN NHẤT.
5. Metadata [Thời gian: X] [Loại: Y] giúp phân biệt thông tin mới/cũ - hãy chú ý khi so sánh.

FEW-SHOT VÍ DỤ (cách trả lời đúng):
---
Ví dụ 1:
CÂU HỎI: Điểm chuẩn ngành CNTT PTIT năm 2024?
TRẢ LỜI: Theo thông tin mới nhất [Thời gian: 2024] [Loại: Điểm chuẩn], điểm chuẩn ngành Công nghệ thông tin tại PTIT năm 2024 là 28.5 điểm [Nguồn 1].
---
Ví dụ 2:
CÂU HỎI: Học phí bao nhiêu?
TRẢ LỜI: Học phí dự kiến năm 2024 là 25 triệu đồng/năm [Nguồn 2]. Chi tiết xem thêm tại nguồn tham khảo.
---
Ví dụ 3:
CÂU HỎI: Điểm chuẩn năm 2030?
TRẢ LỜI: Hiện tại tôi chưa có dữ liệu chính xác cho năm 2030. Bạn có muốn xem dữ liệu năm gần nhất (2024) không?
---
"""


def rewrite_and_hyde(query: str, history: list, school_name: str = "") -> tuple:
  
    school_hint = f" tại **{school_name}**" if school_name else ""

    # Build history text (chỉ lấy 4 lượt cuối)
    history_text = "(Không có)"
    if history:
        recent = history[-4:]
        lines = []
        for msg in recent:
            role = "Người dùng" if msg["role"] == "user" else "Trợ lý"
            lines.append(f"{role}: {msg['message']}")
        history_text = "\n".join(lines)

    prompt = f"""Bạn là công cụ xử lý ngôn ngữ cho hệ thống tư vấn tuyển sinh đại học.
Thực hiện ĐÚNG 2 nhiệm vụ, trả về theo format bên dưới. KHÔNG giải thích thêm.

NHIỆM VỤ 1 - VIẾT LẠI CÂU HỎI:
Viết lại câu hỏi thành câu ĐỘC LẬP hoàn chỉnh bằng tiếng Việt.
- Nếu câu hỏi phụ thuộc ngữ cảnh (dùng "nó/đó/này/thế/vậy", thiếu chủ đề)
  → Bổ sung thông tin từ lịch sử để tạo câu hỏi đầy đủ.
- Nếu câu hỏi đã rõ ràng → Giữ NGUYÊN.
- Nếu không liên quan tuyển sinh → Giữ NGUYÊN.

NHIỆM VỤ 2 - TẠO ĐOẠN VĂN GIẢ ĐỊNH (HyDE):
Viết 3-5 câu bằng tiếng Việt, mô tả thông tin CÓ THỂ là câu trả lời{school_hint}.
Đây là câu trả lời GIẢ ĐỊNH dùng để tìm kiếm dữ liệu, không cần chính xác 100%.

LỊCH SỬ HỘI THOẠI:
{history_text}

CÂU HỎI GỐC: {query}

TRẢ VỀ CHÍNH XÁC theo format (KHÔNG thêm gì khác):
REWRITE: <câu hỏi viết lại>
HYDE: <đoạn văn giả định>"""

    try:
        raw = _call_llm("", prompt, max_tokens=300)

        rewritten = query
        hyde = query

        # Parse kết quả bằng regex
        rewrite_match = re.search(r'REWRITE:\s*(.+?)(?=\nHYDE:|\Z)', raw, re.DOTALL)
        hyde_match = re.search(r'HYDE:\s*(.+)', raw, re.DOTALL)

        if rewrite_match:
            r = rewrite_match.group(1).strip()
            if r and len(r) <= 300:
                rewritten = r
        if hyde_match:
            h = hyde_match.group(1).strip()
            if h and len(h) >= 10:
                hyde = h

        print(f"[REWRITE+HYDE] rewritten: {rewritten}")
        print(f"[REWRITE+HYDE] hyde     : {hyde[:120]}...")
        return rewritten, hyde
    except Exception as e:
        print(f"[REWRITE+HYDE] Error: {e}, fallback to original query")
        return query, query


def rerank_docs(query: str, docs: list) -> list:
    """
    Rerank + Filter (Post-Retrieval):
    Dùng LLM chấm điểm mức độ liên quan của từng chunk với câu hỏi.
    - Chỉ giữ chunk có điểm >= 3 (thang 1-5)
    - Sắp xếp theo điểm giảm dần → LLM đọc chunk quan trọng nhất trước
    - Loại bỏ nhiễu → giảm hallucination

    ⚡ FIX: Dùng regex re.findall(r'\\b([1-5])\\b') thay vì raw.split(",")
    để chống LLM thêm text thừa kiểu "Đây là điểm: 4,2,5"
    """
    if not docs:
        return docs

    chunks_text = ""
    for i, doc in enumerate(docs):
        chunks_text += f"[{i+1}] {doc['content'][:800]}\n\n"

    prompt = f"""Chấm điểm mức độ liên quan của từng đoạn văn với câu hỏi.
Thang điểm: 1=không liên quan, 2=ít liên quan, 3=liên quan, 4=khá liên quan, 5=rất liên quan.

QUY TẮC:
- Trả về CHÍNH XÁC {len(docs)} số, cách nhau bằng dấu phẩy.
- KHÔNG giải thích, KHÔNG thêm chữ nào khác. Ví dụ: 4,2,5,1,3

CÂU HỎI: {query}

CÁC ĐOẠN VĂN:
{chunks_text}
ĐIỂM (chỉ số, cách nhau dấu phẩy):"""

    try:
        raw = _call_llm("", prompt, max_tokens=50)

        # ⚡ FIX: Dùng regex lọc CHỈ các số 1-5, bỏ qua mọi text thừa
        # LLM đôi khi viết: "Đây là điểm của bạn: 4,2,5" → vẫn parse đúng
        scores = [int(s) for s in re.findall(r'\b([1-5])\b', raw)]

        if len(scores) != len(docs):
            print(f"[RERANK] ⚠ Parse mismatch: got {len(scores)} scores for {len(docs)} docs")
            print(f"[RERANK]   Raw response: '{raw}'")
            return docs  # fallback: giữ nguyên nếu parse thất bại

        # Gán điểm vào từng doc, sắp xếp giảm dần
        scored = sorted(
            [(doc, scores[i]) for i, doc in enumerate(docs)],
            key=lambda x: x[1], reverse=True
        )
        print(f"[RERANK]   scores   : {[s for _, s in scored]}")

        # Giữ chunk có điểm >= 3, HOẶC chunk là text-match (tìm được bằng keyword search)
        ranked = []
        for doc, s in scored:
            if s >= 3 or doc.get("_text_match"):
                doc["rerank_score"] = s  # Giữ để generate_answer kiểm tra low_confidence
                ranked.append(doc)
        for doc in ranked:
            doc.pop("_text_match", None)

        if not ranked:
            # Fallback: giữ top 3 điểm cao nhất để LLM tự phán đoán
            print(f"[RERANK]   all below threshold -> fallback top 3")
            for doc, s in scored[:3]:
                doc["rerank_score"] = s
                ranked.append(doc)
        return ranked
    except Exception as e:
        print(f"[RERANK] Error: {e}")
        return docs


def generate_answer(
    query: str,
    context_docs: list,
    history: list = None,
    low_confidence: bool = False,
) -> str:
    """
    Dùng Gemini tổng hợp thông tin từ context và sinh câu trả lời.
    - System Instruction: Vai diễn + quy tắc (giảm token)
    - Metadata injection: [Thời gian] [Loại] cho mỗi chunk
    - Chain-of-Thought: Suy nghĩ theo bước trước khi trả lời
    - low_confidence: Khi rerank thấp → hướng dẫn "I don't know"
    """
    from services.vector_search import enrich_context_docs

    # Context Enrichment: metadata injection + sắp xếp theo ngày (mới nhất trước)
    context_docs = enrich_context_docs(context_docs, sort_by_recency=True)

    # Build context với _enriched_content (có [Thời gian] [Loại])
    context_parts = []
    sources_list = []
    for i, doc in enumerate(context_docs):
        source_url = doc.get("source_url", "")
        source_title = doc.get("source_title", "")
        source_label = f"[Nguồn {i+1}]"
        content = doc.get("_enriched_content") or doc["content"]

        if source_url or source_title:
            sources_list.append({
                "label": source_label,
                "title": source_title,
                "url": source_url
            })
        context_parts.append(f"{source_label}\n{content}")

    context = "\n\n---\n\n".join(context_parts)

    sources_text = ""
    if sources_list:
        src_lines = []
        for s in sources_list:
            if s["url"]:
                src_lines.append(f"- {s['label']}: {s['title'] or 'Nguồn'} ({s['url']})")
            elif s["title"]:
                src_lines.append(f"- {s['label']}: {s['title']}")
        sources_text = "\n".join(src_lines)

    history_text = ""
    if history:
        history_lines = []
        for msg in history:
            role = "Người dùng" if msg["role"] == "user" else "Trợ lý"
            history_lines.append(f"{role}: {msg['message']}")
        history_text = "\n".join(history_lines)

    # Chain-of-Thought: Hướng dẫn LLM suy nghĩ theo bước
    q_lower = query.lower()
    cot_extra = ""
    if "điểm chuẩn" in q_lower or "diem chuan" in q_lower:
        cot_extra = "\n- Bước 4: Nếu có BẢNG ĐIỂM NHIỀU NGÀNH → liệt kê ĐẦY ĐỦ tất cả ngành có trong dữ liệu, không bỏ sót."
    cot_instruction = f"""
CHUỖI TƯ DUY (thực hiện ngầm trước khi trả lời):
- Bước 1: Kiểm tra xem năm/ngày người dùng hỏi có trong dữ liệu không (xem [Thời gian: X]).
- Bước 2: Nếu có nhiều đoạn với số liệu khác nhau → chọn đoạn có [Thời gian] mới nhất.
- Bước 3: So sánh với câu hỏi, trích dẫn chính xác số liệu và ghi [Nguồn X].{cot_extra}
"""

    low_conf_instruction = ""
    if low_confidence:
        low_conf_instruction = """
⚠️ ĐỘ TIN CẬY THẤP: Các đoạn tham khảo có mức độ liên quan thấp.
BẮT BUỘC trả lời: "Hiện tại tôi chưa có dữ liệu chính xác cho câu hỏi này. Bạn có muốn xem dữ liệu năm gần nhất không?"
KHÔNG được bịa đặt thông tin.
"""

    user_prompt = f"""LỊCH SỬ HỘI THOẠI:
{history_text if history_text else "(Không có)"}

THÔNG TIN THAM KHẢO (đã có metadata [Thời gian] [Loại]):
{context}

DANH SÁCH NGUỒN:
{sources_text if sources_text else "(Không có URL nguồn)"}

CÂU HỎI: {query}
{cot_instruction}
{low_conf_instruction}

TRẢ LỜI (trích dẫn [Nguồn X] khi sử dụng thông tin):"""

    try:
        text = _call_llm(SYSTEM_INSTRUCTION, user_prompt, max_tokens=1024, temperature=0.1)
        if not text:
            return "Xin lỗi, tôi không thể tạo câu trả lời từ dữ liệu này. Bạn thử hỏi cách khác nhé."
        return text
    except Exception as e:
        err = str(e).lower()
        if "quota" in err or "429" in err or "resource_exhausted" in err or "rate_limit" in err:
            print(f"[LLM] Quota/rate limit: {e}")
            return "Xin lỗi, dịch vụ AI đang hết quota hoặc quá tải. Vui lòng thử lại sau vài phút."
        if "permission" in err or "403" in err or "leaked" in err or "api_key" in err:
            print(f"[LLM] API key error: {e}")
            return "Xin lỗi, API key không hợp lệ hoặc đã bị vô hiệu hóa. Vui lòng kiểm tra file .env."
        print(f"[LLM] Error: {e}")
        return "Xin lỗi, đã xảy ra lỗi khi kết nối LLM. Vui lòng thử lại."
