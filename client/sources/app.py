"""
Chatbot Tư vấn Tuyển sinh - Flask Backend
Áp dụng:
  - Sliding Window Session: Trí nhớ nhẹ (entities + 5 câu gần nhất)
  - thefuzz: Phát hiện câu vô nghĩa / spam
  - Google Gemini: LLM thông minh hơn
  - Gộp Rewrite + HyDE: 1 call thay vì 2
  - Trích dẫn nguồn: Tăng độ uy tín
"""
import os
import sys

# Thêm thư mục gốc (chứa db/, config.py) vào path khi chạy từ sources/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Load .env từ thư mục gốc
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from flask import Flask

from routers import register_routers

app = Flask(__name__)
register_routers(app)

if __name__ == "__main__":
    from config import GEMINI_MODEL
    print("=" * 50)
    print("Chatbot Tư vấn Tuyển sinh")
    print(f"Gemini model: {GEMINI_MODEL}")
    print("http://localhost:5000")
    print("=" * 50)
    debug = os.getenv("FLASK_DEBUG", "1").lower() in ("1", "true")
    app.run(debug=debug, host="0.0.0.0", port=5000)
