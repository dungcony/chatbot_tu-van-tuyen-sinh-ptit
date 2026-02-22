"""
Service prepare - Upload + Embed dữ liệu lên MongoDB
Chunk, upload, rồi embed vector cho chatbot.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sources.models.document import get_collection

CHUNK_SIZE = 800
CHUNK_OVERLAP = 400
MIN_FINAL_CHUNK = CHUNK_SIZE // 2  # Chunk cuối chỉ tạo nếu > 1/2 chunk_size


def chunk_content(
    content: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Chia nội dung thành chunks với overlap. Chunk cuối gộp vào trước nếu <= min_final."""
    chunks = []
    lines = content.splitlines()
    buf, total = [], 0
    overlap_only = False  # buf chỉ là overlap (chưa thêm dòng mới) -> không tạo chunk mới
    for line in lines:
        buf.append(line)
        overlap_only = False
        total += len(line)
        if total >= chunk_size:
            chunks.append("\n".join(buf))
            overlap_chars, overlap_buf = 0, []
            for i in range(len(buf) - 1, -1, -1):
                overlap_buf.insert(0, buf[i])
                overlap_chars += len(buf[i])
                if overlap_chars >= overlap:
                    break
            buf, total = overlap_buf, overlap_chars
            overlap_only = True
    if buf and not overlap_only:
        remainder = "\n".join(buf)
        if total <= MIN_FINAL_CHUNK and chunks:
            chunks[-1] = chunks[-1] + "\n" + remainder
        else:
            chunks.append(remainder)
    return chunks


def extract_meta_from_file(filepath: Path) -> tuple[dict, str]:
    raw = filepath.read_text(encoding="utf-8")
    meta = {"school": None, "source_file": filepath.name, "source_url": None, "source_title": None, "tags": []}
    content = raw
    if "[TITLE]" in raw and "[URL]" in raw and "[META]" in raw:
        parts = raw.split("---", 1)
        content = parts[1].strip() if len(parts) > 1 else raw
        lines = parts[0].splitlines()
        for i, line in enumerate(lines):
            if line.strip() == "[TITLE]" and i + 1 < len(lines):
                meta["source_title"] = lines[i + 1].strip()
            if line.strip() == "[URL]" and i + 1 < len(lines):
                meta["source_url"] = lines[i + 1].strip()
            if line.strip() == "[META]":
                for j in range(i + 1, min(i + 6, len(lines))):
                    l = lines[j].strip()
                    if l.startswith("school:"):
                        meta["school"] = l.split(":", 1)[1].strip()
                    if l.startswith("tags:"):
                        meta["tags"] = [t.strip() for t in l.split(":", 1)[1].split(",") if t.strip()]
                break
    return meta, content


def run_prepare(source_dir: Path, clear_first: bool = False, embed_after: bool = True) -> dict:
    """
    Chunk, upload lên MongoDB, rồi embed vector.
    Trả về {ok, uploaded, files, embedded, error}
    """
    col = get_collection()
    if clear_first:
        col.delete_many({})

    files = sorted([f for f in source_dir.glob("*.md") if f.is_file()])
    total_chunks = 0
    for f in files:
        meta, content = extract_meta_from_file(f)
        chunks = chunk_content(content)
        for idx, chunk in enumerate(chunks):
            doc = {
                "content": chunk,
                "school": meta["school"],
                "source_file": meta["source_file"],
                "source_url": meta["source_url"],
                "source_title": meta["source_title"],
                "tags": meta["tags"],
                "chunk_id": idx + 1,
                "total_chunks": len(chunks),
                "embedding": None,
            }
            col.insert_one(doc)
            total_chunks += 1

    embedded = 0
    if embed_after and total_chunks > 0:
        from sources.services.embed_service import embed_documents
        result = embed_documents()
        embedded = result.get("embedded", 0)
        if result.get("error"):
            return {
                "ok": False,
                "uploaded": total_chunks,
                "files": len(files),
                "embedded": 0,
                "error": f"Upload OK nhưng embed lỗi: {result['error']}",
            }

    return {
        "ok": True,
        "uploaded": total_chunks,
        "files": len(files),
        "embedded": embedded,
        "error": None,
    }
