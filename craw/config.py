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

# ── Embedding ──────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)