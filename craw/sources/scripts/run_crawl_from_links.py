#!/usr/bin/env python3
"""
Crawl dữ liệu từ các link trong folder links/*.json hoặc nhập URL.
Hỗ trợ nhiều loại nội dung:
- Dạng bảng (HTML table, ảnh bảng qua OCR)
- Dạng ảnh (OCR nếu là bảng điểm)
- Dạng video (lưu metadata)
- Dạng file (PDF, Word, Excel - trích xuất text)

Chạy: python run_crawl_from_links.py --mode json|url
"""
import argparse
from pathlib import Path
import json
import time
import sys
import re

# Setup path for services
PROJECT_DIR = Path(__file__).resolve().parent.parent
ROOT = PROJECT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

# Thư mục: links trong public/links, data trong public/data
LINKS_DIR = ROOT / "public" / "links"
DATA_DIR = ROOT / "public" / "data"
FILES_DIR = DATA_DIR / "files"
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / "crawl_state_links.json"

# Modular crawl utilities from services.crawls
from services.crawls import (
    load_all_links, load_state, save_state, crawl_html_page, url_to_filename,
    extract_pdf, extract_docx, extract_xlsx, extract_json,
    get_video_metadata, ocr_image_table, get_image_metadata
)
from services.normalize.content_handlers import detect_content_type, extract_content, download_file

MIN_CONTENT_LENGTH = 150


_SAFE_SEGMENT = re.compile(r"[^\w\-]+", re.UNICODE)


def _safe_path_segment(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "_"
    text = _SAFE_SEGMENT.sub("_", text)
    text = text.strip("_-")
    return text[:80] or "_"


def _category_dir(base: Path, category: str | None) -> Path:
    """Map category string like 'a/b/c' to nested safe folders."""
    if not category:
        return base / "_root"
    parts = [p for p in str(category).split("/") if p and p not in (".", "..")]
    safe_parts = [_safe_path_segment(p) for p in parts]
    return base.joinpath(*safe_parts) if safe_parts else (base / "_root")


def run_crawl(source_filter: str | None = None, max_pages: int = 500, download_files: bool = True):
    sources = load_all_links(LINKS_DIR, source_filter)
    if not sources:
        print("Không tìm thấy file .json trong links/ hoặc không khớp --source")
        return

    state = load_state(STATE_FILE)
    crawled_set = set(state["crawled"])
    failed_set = set(state["failed"])

    # Build queue
    queue = []
    for source_id, items in sources.items():
        for item in items:
            url = item["url"]
            key = f"{source_id}|{url}"
            if key not in crawled_set and key not in failed_set:
                queue.append({"source_id": source_id, "url": url, "category": item.get("category", "")})

    if not queue:
        print("Tất cả link đã được crawl.")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)

    new_crawled = 0
    new_failed = 0
    downloaded_files = set()

    print(f"Crawl {min(len(queue), max_pages)} URL từ links/ (max={max_pages})...")

    for i, item in enumerate(queue):
        if i >= max_pages:
            break

        source_id = item["source_id"]
        url = item["url"]
        category = item.get("category", "")
        key = f"{source_id}|{url}"

        # Output folder: public/data/<source_id>/<category>/...
        out_base = DATA_DIR / source_id
        out_dir = _category_dir(out_base, category)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Download folder (attachments): public/data/files/<source_id>/<category>/...
        dl_dir = _category_dir(FILES_DIR / source_id, category)
        dl_dir.mkdir(parents=True, exist_ok=True)

        content_type = detect_content_type(url)

        # HTML
        if content_type == "html":
            text, file_urls = crawl_html_page(url)
            if text:
                filepath = out_dir / url_to_filename(source_id, url, "md")
                filepath.write_text(text.rstrip() + "\n", encoding="utf-8")
                crawled_set.add(key)
                new_crawled += 1
                rel = filepath.relative_to(DATA_DIR)
                print(f"  OK [HTML] [{source_id}] {rel} ({len(text)} chars)")
                if download_files and file_urls:
                    for file_url in file_urls:
                        if file_url in downloaded_files:
                            continue
                        saved = download_file(file_url, dl_dir)
                        if saved:
                            downloaded_files.add(file_url)
                            print(f"    -> File: {saved.name}")
            else:
                failed_set.add(key)
                new_failed += 1
                print(f"  FAIL [{source_id}] {url[:60]}...")

        # PDF, Word, Excel
        elif content_type in ("pdf", "docx", "xlsx", "doc", "xls"):
            text, _ = extract_content(url, content_type)
            if text and len(text) >= MIN_CONTENT_LENGTH:
                filepath = out_dir / url_to_filename(source_id, url, "md")
                header = f"[URL: {url}]\n[Loại: {content_type}]\n\n"
                filepath.write_text((header + text).rstrip() + "\n", encoding="utf-8")
                crawled_set.add(key)
                new_crawled += 1
                rel = filepath.relative_to(DATA_DIR)
                print(f"  OK [{content_type.upper()}] [{source_id}] {rel}")
                if download_files:
                    saved = download_file(url, dl_dir)
                    if saved:
                        print(f"    -> Đã tải: {saved.name}")
            else:
                if download_files:
                    saved = download_file(url, dl_dir)
                    if saved:
                        crawled_set.add(key)
                        new_crawled += 1
                        print(f"  OK [FILE] [{source_id}] Đã tải: {saved.name}")
                    else:
                        failed_set.add(key)
                        new_failed += 1
                else:
                    failed_set.add(key)
                    new_failed += 1

        # Ảnh
        elif content_type == "image":
            text = ocr_image_table(url)
            if text:
                filepath = out_dir / url_to_filename(source_id, url, "md")
                header = f"[URL: {url}]\n[Loại: ảnh - OCR]\n\n"
                filepath.write_text((header + text).rstrip() + "\n", encoding="utf-8")
                crawled_set.add(key)
                new_crawled += 1
                rel = filepath.relative_to(DATA_DIR)
                print(f"  OK [IMAGE/OCR] [{source_id}] {rel}")
            else:
                meta = get_image_metadata(url)
                filepath = out_dir / url_to_filename(source_id, url, "json")
                filepath.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                crawled_set.add(key)
                new_crawled += 1
                rel = filepath.relative_to(DATA_DIR)
                print(f"  OK [IMAGE] [{source_id}] metadata: {rel}")

        # Video
        elif content_type == "video":
            meta = get_video_metadata(url)
            filepath = out_dir / url_to_filename(source_id, url, "json")
            filepath.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            crawled_set.add(key)
            new_crawled += 1
            rel = filepath.relative_to(DATA_DIR)
            print(f"  OK [VIDEO] [{source_id}] metadata: {rel}")

        else:
            failed_set.add(key)
            new_failed += 1
            print(f"  SKIP [{content_type}] [{source_id}] {url[:50]}...")

        time.sleep(1)

    save_state(STATE_FILE, {"crawled": list(crawled_set), "failed": list(failed_set)})
    print(f"\nXong: {new_crawled} mới, {new_failed} lỗi. Dữ liệu: {DATA_DIR}")


def run_crawl_from_json(json_file: Path, max_pages: int = 500, download_files: bool = True):
    return run_crawl(source_filter=json_file.stem, max_pages=max_pages, download_files=download_files)


def run_crawl_from_url(url: str, download_files: bool = True):
    from services.normalize.content_handlers import detect_content_type
    from services.crawls import crawl_html_page, url_to_filename, extract_pdf, extract_docx, extract_xlsx, extract_json, get_video_metadata, ocr_image_table, get_image_metadata
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    source_id = "manual"
    out_dir = DATA_DIR / source_id / "_root"
    out_dir.mkdir(parents=True, exist_ok=True)
    dl_dir = FILES_DIR / source_id / "_root"
    dl_dir.mkdir(parents=True, exist_ok=True)
    content_type = detect_content_type(url)
    if content_type == "html":
        text, file_urls = crawl_html_page(url)
        if text:
            filepath = out_dir / url_to_filename(source_id, url, "md")
            filepath.write_text(text.rstrip() + "\n", encoding="utf-8")
            print(f"  OK [HTML] {filepath.name} ({len(text)} chars)")
        else:
            print(f"  FAIL [HTML] {url[:60]}...")
    elif content_type in ("pdf", "docx", "xlsx", "doc", "xls"):
        text, _ = extract_content(url, content_type)
        if text:
            filepath = out_dir / url_to_filename(source_id, url, "md")
            header = f"[URL: {url}]\n[Loại: {content_type}]\n\n"
            filepath.write_text((header + text).rstrip() + "\n", encoding="utf-8")
            print(f"  OK [{content_type.upper()}] {filepath.name}")
        else:
            print(f"  FAIL [{content_type.upper()}] {url[:60]}...")
    elif content_type == "image":
        text = ocr_image_table(url)
        if text:
            filepath = out_dir / url_to_filename(source_id, url, "md")
            header = f"[URL: {url}]\n[Loại: ảnh - OCR]\n\n"
            filepath.write_text((header + text).rstrip() + "\n", encoding="utf-8")
            print(f"  OK [IMAGE/OCR] {filepath.name}")
        else:
            meta = get_image_metadata(url)
            filepath = out_dir / url_to_filename(source_id, url, "json")
            filepath.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  OK [IMAGE] metadata: {filepath.name}")
    elif content_type == "video":
        meta = get_video_metadata(url)
        filepath = out_dir / url_to_filename(source_id, url, "json")
        filepath.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  OK [VIDEO] metadata: {filepath.name}")
    else:
        print(f"  SKIP [{content_type}] {url[:50]}...")


def main():
    ap = argparse.ArgumentParser(description="Crawl từ links/*.json hoặc nhập URL")
    ap.add_argument("--mode", choices=["json", "url"], default="json", help="Chọn chế độ crawl: json hoặc url")
    ap.add_argument("--file", help="Tên file .json trong links/ (chỉ dùng cho mode=json)")
    ap.add_argument("--url", help="URL để crawl (chỉ dùng cho mode=url)")
    ap.add_argument("--max", type=int, default=500, help="Số trang tối đa")
    ap.add_argument("--no-download", action="store_true", help="Không tải file PDF/Word về")
    args = ap.parse_args()
    if args.mode == "json":
        if not args.file:
            files = list(LINKS_DIR.glob("*.json"))
            print("Chọn file .json để crawl:")
            for idx, f in enumerate(files):
                print(f"  [{idx+1}] {f.name}")
            sel = input("Nhập số thứ tự file: ").strip()
            try:
                idx = int(sel) - 1
                json_file = files[idx]
            except Exception:
                print("Lựa chọn không hợp lệ.")
                return
        else:
            json_file = LINKS_DIR / args.file
            if not json_file.exists():
                print(f"Không tìm thấy file: {json_file}")
                return
        run_crawl_from_json(json_file, max_pages=args.max, download_files=not args.no_download)
    elif args.mode == "url":
        if not args.url:
            url = input("Nhập URL để crawl: ").strip()
        else:
            url = args.url
        run_crawl_from_url(url, download_files=not args.no_download)

if __name__ == "__main__":
    main()
