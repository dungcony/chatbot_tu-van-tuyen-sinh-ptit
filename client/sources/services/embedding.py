"""
4.2.1 Cấu hình lớp Embedding (Hình 4.2.1)
Định nghĩa cấu hình và lớp chính để tạo và sử dụng mô hình embedding từ SentenceTransformer.
"""
from sentence_transformers import SentenceTransformer

from pydantic import BaseModel, Field, field_validator


class EmbeddingConfig(BaseModel):
    """Lớp kế thừa từ BaseModel của Pydantic, định nghĩa cấu hình cho mô hình embedding."""

    name: str = Field(..., description="Tên mô hình SentenceTransformer")

    @field_validator("name")
    @classmethod
    def check_model_name(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("Model name must be a non-empty string")
        return v


class MainEmbedding:
    """Lớp chứa logic chính để sử dụng mô hình SentenceTransformer."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.embedding_model = SentenceTransformer(self.config.name)

    def encode(self, text: str):
        """Tạo embedding từ chuỗi văn bản."""
        return self.embedding_model.encode(text)

    def embed_query(self, query: str) -> list:
        """Tạo embedding cho query (tương thích LangChain). Trả về list float cho vector search."""
        return self.embedding_model.encode(query).tolist()


# Singleton
_instance: MainEmbedding | None = None


def get_embedding_model(embedding_name: str | None = None) -> MainEmbedding:
    """Trả về embedding model (khởi tạo 1 lần duy nhất)."""
    global _instance
    if _instance is None:
        from config import EMBEDDING_MODEL
        name = embedding_name or EMBEDDING_MODEL
        print(f"Đang khởi tạo Embedding Model ({name})...")
        _instance = MainEmbedding(EmbeddingConfig(name=name))
        print("Embedding Model sẵn sàng!")
    return _instance
