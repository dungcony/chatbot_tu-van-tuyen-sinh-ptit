"""
Cấu hình trung tâm - Load từ file .env
Chỉ chứa config cấp môi trường (secrets, connection strings).
Application constants (collection names, index names) nằm ở từng service.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable not set. Check .env file.")
DB_NAME = os.getenv("DB_NAME", "tuvantuyensinh")

# ── LLM Provider (doi trong .env, khong can sua code) ──────────────────
# LLM_PROVIDER: gemini | groq | ollama | openai
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
LLM_BASE_URL  = os.getenv("LLM_BASE_URL", "")   # VD: https://api.groq.com/openai/v1
LLM_API_KEY   = os.getenv("LLM_API_KEY", "")    # API key cua provider
LLM_MODEL     = os.getenv("LLM_MODEL", "")      # VD: llama-3.3-70b-versatile

# ── Embedding ──────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "auto")

# ── Session (Sliding Window) ──────────────────────────────────────────
SLIDING_WINDOW_SIZE = int(os.getenv("SLIDING_WINDOW_SIZE", "5"))
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "3600"))
