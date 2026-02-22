"""
Embedding Model - Singleton
Dùng chung 1 instance cho toàn bộ ứng dụng để tránh load model nhiều lần.
Model: paraphrase-multilingual-mpnet-base-v2 (768 chiều)
"""

from langchain_huggingface import HuggingFaceEmbeddings
from config import EMBEDDING_MODEL

_model = None


def get_embedding_model():
    """Trả về embedding model (khởi tạo 1 lần duy nhất)."""
    global _model
    if _model is None:
        print("Đang khởi tạo Embedding Model...")
        _model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        print("Embedding Model sẵn sàng!")
    return _model
