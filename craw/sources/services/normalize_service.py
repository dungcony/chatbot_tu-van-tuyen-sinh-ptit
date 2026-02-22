"""
Service normalize - Xử lý dữ liệu theo file hoặc folder
"""
import json
import sys
from pathlib import Path

# Add sources to path
SOURCES = Path(__file__).resolve().parent.parent
if str(SOURCES) not in sys.path:
    sys.path.insert(0, str(SOURCES))

from services.normalize import (
    norm_meta, norm_clean_content, norm_clean_html,
    norm_tables, norm_metadata, norm_dedup, norm_synonyms
)

PROCESSOR_KEYS = ["meta", "clean_content", "clean_html", "tables", "metadata", "dedup", "synonyms"]


def process_single_file(filepath: Path, steps: list[str], output_dir: Path, hashes: dict) -> dict:
    """Xử lý 1 file qua các bước normalize."""
    filename = filepath.name
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    content = raw_text
    source_url = ""
    source_title = ""
    tags = []
    year = None
    doc_hash = ""
    school = "unknown"

    if "meta" in steps:
        content, source_url, source_title = norm_meta.extract_meta_header(content)
    if "clean_content" in steps:
        content = norm_clean_content.clean_content(content)
    if "clean_html" in steps:
        content = norm_clean_html.clean_html_and_special_chars(content)
    if "tables" in steps:
        try:
            content = norm_tables.process_tables(content)
        except Exception:
            pass
    if "metadata" in steps:
        tags = norm_metadata.detect_metadata_tags(content)
        year = norm_metadata.detect_year(content)
    if "dedup" in steps:
        doc_hash = norm_dedup.content_hash(content)
        if doc_hash in hashes and hashes[doc_hash] != filename:
            return {"status": "dup", "message": f"trùng với {hashes[doc_hash]}", "hash": doc_hash}
        hashes[doc_hash] = filename
    else:
        doc_hash = norm_dedup.content_hash(content)
    if "synonyms" in steps:
        content = norm_synonyms.expand_synonyms(content)
    school = norm_meta.extract_school(filename)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_lines = []
    if "meta" in steps:
        out_lines += ["[TITLE]", source_title or filename, "", "[URL]", source_url, ""]
    if "metadata" in steps or "dedup" in steps:
        out_lines += ["[META]", f"school: {school}", f"tags: {','.join(tags)}", f"year: {year or ''}", f"hash: {doc_hash}", ""]
    if out_lines:
        out_lines += ["---", ""]
    out_lines.append(content)
    out_path = output_dir / filename
    out_path.write_text("\n".join(out_lines), encoding="utf-8")
    return {"status": "ok", "message": str(out_path), "tags": tags[:4], "year": year, "chars": len(content)}


def run_normalize(
    input_dir: Path,
    output_dir: Path,
    mode: str,  # "file" | "folder"
    file_name: str | None = None,
    steps: list[str] | None = None,
) -> dict:
    """
    Chạy normalize. Trả về {ok, output, stats: {ok, dup, err}}
    """
    steps = steps or PROCESSOR_KEYS
    hashes = {}
    hash_file = output_dir / ".content_hashes.json"
    if hash_file.exists():
        try:
            hashes = json.loads(hash_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    if mode == "file" and file_name:
        files = [input_dir / file_name]
        if not files[0].exists():
            return {"ok": False, "output": "File không tồn tại", "stats": {"ok": 0, "dup": 0, "err": 1}}
    else:
        files = sorted(
            f for f in input_dir.iterdir()
            if f.is_file() and f.suffix in (".md", ".txt") and not f.name.startswith(".")
        )

    stats = {"ok": 0, "dup": 0, "err": 0}
    lines = []
    for f in files:
        try:
            r = process_single_file(f, steps, output_dir, hashes)
            stats[r["status"]] = stats.get(r["status"], 0) + 1
            lines.append(f"[{r['status'].upper()}] {f.name}: {r.get('message', '')}")
        except Exception as e:
            stats["err"] += 1
            lines.append(f"[ERR] {f.name}: {e}")

    if "dedup" in steps:
        output_dir.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, "output": "\n".join(lines), "stats": stats}
