"""
Lightweight Session Manager - Cửa sổ trượt (Sliding Window)

Quản lý "trí nhớ nhẹ" cho chatbot:
  1. Entities (thông tin lõi): Tên trường, tên ngành... chỉ tốn vài byte.
  2. Sliding Window (lịch sử ngắn): Giữ đúng N câu gần nhất để hiểu mạch nói chuyện.

Dữ liệu lưu in-memory (dict), không cần DB → cực nhanh, cực nhẹ.
Session tự dọn dẹp sau SESSION_MAX_AGE giây không hoạt động.
"""

from collections import defaultdict
import time
from config import SLIDING_WINDOW_SIZE, SESSION_MAX_AGE


class LightweightSession:
    """
    Mỗi session_id có:
      - entities: dict chứa thông tin lõi (school, program, ...)
      - history: list các message gần nhất (sliding window)
      - last_active: timestamp lần cuối hoạt động
    """

    def __init__(self):
        self._sessions = defaultdict(lambda: {
            "entities": {},       # Thông tin lõi: school, program, ...
            "history": [],        # Sliding window: N message gần nhất
            "last_active": 0.0
        })

    # ── Entity Management ──────────────────────────────────────────────

    def get_entities(self, session_id: str) -> dict:
        """Lấy toàn bộ entities của session."""
        return self._sessions[session_id]["entities"]

    def update_entities(self, session_id: str, **kwargs):
        """Cập nhật entities (merge, không ghi đè toàn bộ)."""
        session = self._sessions[session_id]
        session["entities"].update(kwargs)
        session["last_active"] = time.time()

    def set_school(self, session_id: str, school_id: str):
        """Lưu trường đang focus."""
        self.update_entities(session_id, school=school_id)

    def get_school(self, session_id: str) -> str:
        """Lấy trường đang focus (hoặc None)."""
        return self._sessions[session_id]["entities"].get("school")

    def set_program(self, session_id: str, program: str):
        """Lưu ngành đang hỏi."""
        self.update_entities(session_id, program=program)

    def get_program(self, session_id: str) -> str:
        """Lấy ngành đang hỏi (hoặc None)."""
        return self._sessions[session_id]["entities"].get("program")

    # ── Sliding Window History ─────────────────────────────────────────

    def add_message(self, session_id: str, role: str, message: str):
        """
        Thêm message vào history, tự động cắt nếu vượt SLIDING_WINDOW_SIZE.
        role: "user" | "bot"
        """
        session = self._sessions[session_id]
        session["history"].append({"role": role, "message": message})

        # ⚡ Sliding window: chỉ giữ N message gần nhất
        if len(session["history"]) > SLIDING_WINDOW_SIZE:
            session["history"] = session["history"][-SLIDING_WINDOW_SIZE:]

        session["last_active"] = time.time()

    def get_history(self, session_id: str, limit: int = None) -> list:
        """
        Lấy lịch sử hội thoại (sliding window).
        limit: số message tối đa (default = SLIDING_WINDOW_SIZE)
        """
        if limit is None:
            limit = SLIDING_WINDOW_SIZE
        return self._sessions[session_id]["history"][-limit:]

    # ── Session Lifecycle ──────────────────────────────────────────────

    def clear_session(self, session_id: str):
        """Xóa toàn bộ session."""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def cleanup_old_sessions(self):
        """Dọn dẹp sessions không hoạt động quá SESSION_MAX_AGE giây."""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s["last_active"] > SESSION_MAX_AGE
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            print(f"[SESSION] Cleaned up {len(expired)} expired sessions")

    def get_session_summary(self, session_id: str) -> dict:
        """Debug: Xem tóm tắt session."""
        session = self._sessions[session_id]
        return {
            "entities": session["entities"],
            "history_length": len(session["history"]),
            "last_active": session["last_active"]
        }


# ── Singleton ──────────────────────────────────────────────────────────
session_manager = LightweightSession()
