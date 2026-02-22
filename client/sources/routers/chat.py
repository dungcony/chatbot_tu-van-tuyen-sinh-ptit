"""
Chat Router - Route / và /chat
Logic xử lý nằm ở chat_handler.py
"""
import os
from flask import Blueprint, request, jsonify, render_template

from routers.chat_handler import (
    check_intent,
    is_school_selection,
    resolve_school,
    handle_intent_nonsense,
    handle_intent_greeting,
    handle_intent_confirm,
    handle_school_selection,
    handle_no_school,
    handle_rag,
)
from utils.session import session_manager

# Cấu hình Blueprint: templates và static từ thư mục pages
PAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pages")
bp = Blueprint(
    "chat",
    __name__,
    template_folder=PAGES_DIR,
    static_folder=PAGES_DIR,
    static_url_path="/pages",
)


@bp.route("/")
def index():
    return render_template("client.html")


@bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    query = data.get("message", "").strip()
    session_id = data.get("session_id", "default")

    if not query:
        return jsonify({"error": "Vui long nhap cau hoi"}), 400

    try:
        intent = check_intent(query)

        # Intent đặc biệt: NONSENSE, GREETING, CONFIRM
        if intent == "NONSENSE":
            answer, sources = handle_intent_nonsense(query, session_id)
            return jsonify({"answer": answer, "sources": sources})
        if intent == "GREETING":
            answer, sources = handle_intent_greeting(query, session_id)
            return jsonify({"answer": answer, "sources": sources})
        if intent == "CONFIRM":
            answer, sources = handle_intent_confirm(query, session_id)
            return jsonify({"answer": answer, "sources": sources})

        # Luồng chính: cần xác định trường
        session_manager.add_message(session_id, "user", query)
        school = resolve_school(query, session_id)

        if school and is_school_selection(query):
            answer, sources = handle_school_selection(query, session_id, school)
            return jsonify({"answer": answer, "sources": sources})
        if not school:
            answer, sources = handle_no_school(session_id)
            return jsonify({"answer": answer, "sources": sources})

        # RAG pipeline
        answer, sources = handle_rag(query, session_id, school)
        return jsonify({"answer": answer, "sources": sources})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Đã xảy ra lỗi khi xử lý. Vui lòng thử lại."}), 500
