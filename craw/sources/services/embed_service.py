"""
Service embedding - Tạo vector cho documents trong MongoDB
Dùng MainEmbedding từ embedding.py (EmbeddingConfig, get_embedding_model).
"""
from sources.models.document import get_collection
from sources.services.embedding import get_embedding_model


def _build_embedding_text(doc: dict) -> str:
    """Build the text that will be embedded for a document.

    We keep MongoDB `content` unchanged for display, but can add lightweight
    metadata (like year) to the embedding input to improve retrieval.
    """
    content = (doc.get("content") or "").strip()
    year = doc.get("year")
    year_str = str(year).strip() if year is not None else ""
    if year_str:
        return f"Năm: {year_str}\n{content}" if content else f"Năm: {year_str}"
    return content


def embed_documents(batch_size: int = 32) -> dict:
    """
    Embed tất cả documents có embedding=None.
    Trả về: {embedded: int, total: int, error: str|None}
    """
    col = get_collection()
    cursor = col.find({"embedding": None})
    docs = list(cursor)
    total = len(docs)
    if total == 0:
        return {"embedded": 0, "total": 0, "error": None}

    try:
        model = get_embedding_model()
    except Exception as e:
        return {"embedded": 0, "total": total, "error": str(e)}

    embedded = 0
    for i in range(0, total, batch_size):
        batch = docs[i : i + batch_size]
        texts = [_build_embedding_text(d) for d in batch]
        vectors = model.encode(texts)
        for j, doc in enumerate(batch):
            col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"embedding": vectors[j].tolist()}},
            )
            embedded += 1
    return {"embedded": embedded, "total": total, "error": None}


def count_unembedded() -> int:
    """Đếm số documents chưa có embedding."""
    return get_collection().count_documents({"embedding": None})
