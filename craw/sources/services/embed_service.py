"""
Service embedding - Tạo vector cho documents trong MongoDB
"""
from sources.models.document import get_collection


def get_embedder():
    """Lazy load SentenceTransformer."""
    try:
        from sentence_transformers import SentenceTransformer
        from config import EMBEDDING_MODEL
        return SentenceTransformer(EMBEDDING_MODEL)
    except ImportError:
        raise RuntimeError(
            "Cần cài sentence-transformers: pip install sentence-transformers"
        )


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
        model = get_embedder()
    except Exception as e:
        return {"embedded": 0, "total": total, "error": str(e)}

    embedded = 0
    for i in range(0, total, batch_size):
        batch = docs[i : i + batch_size]
        texts = [d.get("content") or "" for d in batch]
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
