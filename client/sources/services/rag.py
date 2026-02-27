"""
4.2 Triển khai RAG (Hình 4.2.2)
Lớp RAG: kết nối MongoDB, embedding model, LLM.
Phương thức Vector Search: tạo embedding từ query → pipeline tìm kiếm → trả về kết quả.
"""
import pymongo
from services.embedding import MainEmbedding, EmbeddingConfig
from models.document import COLLECTION_NAME, VECTOR_INDEX_NAME


class RAG:
    """
    Lớp RAG theo thiết kế báo cáo.
    - __init__: Khởi tạo MongoDB client, embedding model, LLM.
    - vector_search: Tìm kiếm vector theo query.
    - retrieve: Pipeline đầy đủ (dual search + text search + merge).
    - generate: Sinh câu trả lời từ context.
    """

    def __init__(self, mongodb_uri: str, db_name: str, llm, embedding_name: str):
        """
        Khởi tạo RAG.
        :param mongodb_uri: URI kết nối MongoDB
        :param db_name: Tên database
        :param llm: Large Language Model (dùng cho generate)
        :param embedding_name: Tên mô hình embedding (SentenceTransformer)
        """
        self.client = pymongo.MongoClient(mongodb_uri)
        self.db = self.client[db_name]
        self.embedding_model = MainEmbedding(EmbeddingConfig(name=embedding_name))
        self.llm = llm
        self._collection = self.db[COLLECTION_NAME]

    def vector_search(
        self,
        query: str,
        school=None,
        tags=None,
        num_candidates: int = 200,
        limit: int = 6,
        score_threshold: float = 0.55,
    ) -> list:
        """
        Phương thức Vector Search (Hình 4.2.2).
        - Tạo embedding từ truy vấn người dùng.
        - Pipeline: vector_search_stage → project_stage (content, tags, score).
        - Thực hiện truy vấn và trả về kết quả.
        """
        from pymongo.errors import OperationFailure

        # Tạo embedding từ query
        query_vector = self.embedding_model.embed_query(query)

        vs_filter = {}
        if school:
            vs_filter["school"] = school
        if tags:
            vs_filter["tags"] = {"$in": tags}

        vector_search_stage = {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": limit,
            }
        }
        if vs_filter:
            vector_search_stage["$vectorSearch"]["filter"] = vs_filter

        # project_stage: chọn các trường cần thiết (content, tags, score)
        project_stage = {
            "$project": {
                "_id": 0,
                "content": 1,
                "school": 1,
                "tags": 1,
                "source_url": 1,
                "source_title": 1,
                "source_file": 1,
                "source_date": 1,
                "questions": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        }

        pipeline = [vector_search_stage, project_stage]

        try:
            results = list(self._collection.aggregate(pipeline))
        except OperationFailure as e:
            if "needs to be indexed as filter" in str(e):
                vector_search_stage["$vectorSearch"].pop("filter", None)
                vector_search_stage["$vectorSearch"]["limit"] = limit * 5
                results = list(self._collection.aggregate(pipeline))
                if school:
                    results = [d for d in results if self._school_matches(d.get("school", ""), school)]
                if tags:
                    results = [d for d in results if d.get("tags") and set(d["tags"]) & set(tags)]
                results = results[:limit]
            else:
                raise

        return [doc for doc in results if doc.get("score", 0) >= score_threshold]

    def _school_matches(self, doc_school: str, query_school: str) -> bool:
        s1 = (doc_school or "").strip().rstrip("/") or ""
        s2 = (query_school or "").strip().rstrip("/") or ""
        return s1 == s2

    def retrieve(
        self,
        original_query: str,
        hyde_query: str,
        school=None,
        num_candidates: int = 200,
        limit: int = 10,
        score_threshold: float = 0.55,
    ) -> list:
        """
        Pipeline retrieve đầy đủ: dual vector search + text search + merge.
        Dùng cho handle_rag.
        """
        from services.vector_search import (
            _detect_program_name,
            _text_search_score_docs,
            _merge_results,
            _boost_by_questions_match,
        )

        # Dual search: original + HyDE
        results_orig = self.vector_search(
            original_query, school=school,
            num_candidates=num_candidates, limit=limit,
            score_threshold=score_threshold,
        )
        results_hyde = self.vector_search(
            hyde_query, school=school,
            num_candidates=num_candidates, limit=limit,
            score_threshold=score_threshold,
        )

        # Text search (bảng điểm theo tên ngành)
        program_name = _detect_program_name(original_query)
        text_results = []
        if program_name and school:
            try:
                text_results = _text_search_score_docs(
                    self._collection, school, program_name, tags=None, limit=5
                )
                if text_results:
                    print(f"[DUAL-SEARCH] text-search ({program_name}): {len(text_results)} results")
            except Exception as e:
                print(f"[DUAL-SEARCH] text-search failed: {e}")

        merged = _merge_results(text_results, [results_orig, results_hyde], max_results=limit)
        print(f"[DUAL-SEARCH] merged total: {len(merged)} results")

        merged = _boost_by_questions_match(merged, original_query)
        return merged

    def generate(
        self,
        query: str,
        context_docs: list,
        history: list = None,
        low_confidence: bool = False,
    ) -> str:
        """Sinh câu trả lời từ context (delegate tới generate_answer)."""
        from services.llm import generate_answer
        return generate_answer(query, context_docs, history=history, low_confidence=low_confidence)


# Singleton RAG instance
_rag_instance: RAG | None = None


def get_rag() -> RAG:
    """Trả về instance RAG (khởi tạo 1 lần duy nhất)."""
    global _rag_instance
    if _rag_instance is None:
        from config import MONGO_URI, DB_NAME, EMBEDDING_MODEL
        print("Đang khởi tạo RAG...")
        _rag_instance = RAG(
            mongodb_uri=MONGO_URI,
            db_name=DB_NAME,
            llm=None,  # generate_answer dùng config riêng
            embedding_name=EMBEDDING_MODEL,
        )
        print("RAG sẵn sàng!")
    return _rag_instance
