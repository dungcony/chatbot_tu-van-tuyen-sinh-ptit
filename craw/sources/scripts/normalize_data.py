#!/usr/bin/env python3
"""
Service xử lý (normalize) dữ liệu crawl.
Chạy:  python services/normalize_data.py

2 lựa chọn chính:
  1. Xử lý 1 file  → chọn folder → chọn file
  2. Xử lý 1 folder → chọn folder

Sau đó chọn các bước xử lý (chọn nhiều hoặc all).
"""
import json
import os
import sys
from pathlib import Path

# Setup path for services
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

# Import normalization modules from services.normalize
from services.normalize import (
    norm_meta, norm_clean_content, norm_clean_html,
    norm_tables, norm_metadata, norm_dedup, norm_synonyms
)

# ── Thư mục mặc định ───────────────────────────────────────
DEFAULT_INPUT_DIR = PROJECT_DIR / "data"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "nor"
HASH_FILE = DEFAULT_OUTPUT_DIR / ".content_hashes.json"

# ── Màu terminal ────────────────────────────────────────────
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[92m"
C_CYAN = "\033[96m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_DIM = "\033[2m"


# ═══════════════════════════════════════════════════════════
#  Danh sách các bước xử lý
# ═══════════════════════════════════════════════════════════
PROCESSORS = {
    "meta": {
        "name": "Tách metadata (title, URL, school)",
        "desc": "Tách [Title][URL:...] ra khỏi nội dung",
    },
    "clean_content": {
        "name": "Xóa menu nav / footer / dòng rác",
        "desc": "Xóa block menu (*/+/-), cắt footer, lọc spam",
    },
    "clean_html": {
        "name": "Xóa HTML & ký tự đặc biệt",
        "desc": "Decode &nbsp;, xóa thẻ HTML sót, chuẩn khoảng trắng",
    },
    "tables": {
        "name": "Chuẩn hóa bảng biểu",
        "desc": "Sửa typo, gộp orphan, chuyển bảng sang mô tả ngữ nghĩa",
    },
    "metadata": {
        "name": "Gắn tags & phát hiện năm",
        "desc": "Gán nhãn diem_chuan, hoc_phi, nganh_hoc..., detect year",
    },
    "dedup": {
        "name": "Dedup (hash nội dung)",
        "desc": "Tạo MD5 hash, bỏ qua nếu nội dung trùng",
    },
    "synonyms": {
        "name": "Mở rộng từ viết tắt",
        "desc": "HSA→Đánh giá năng lực, SAT→Scholastic Assessment Test...",
    },
}

PROCESSOR_KEYS = list(PROCESSORS.keys())


# ═══════════════════════════════════════════════════════════
#  Tiện ích UI
# ═══════════════════════════════════════════════════════════
def print_header(title: str):
    w = 56
    print()
    print(f"{C_CYAN}{'═' * w}")
    print(f"  {C_BOLD}{title}{C_RESET}{C_CYAN}")
    print(f"{'═' * w}{C_RESET}")


def print_menu(options: list[str], *, start=1, show_zero: str | None = None):
    """In danh sách lựa chọn có đánh số."""
    if show_zero:
        print(f"  {C_YELLOW}[0]{C_RESET} {show_zero}")
    for i, opt in enumerate(options, start):
        print(f"  {C_YELLOW}[{i}]{C_RESET} {opt}")


def input_choice(prompt: str, max_val: int, *, min_val: int = 1, allow_zero=False) -> int:
    """Nhập 1 số trong khoảng."""
    while True:
        try:
            raw = input(f"\n{C_GREEN}▸ {prompt}: {C_RESET}").strip()
            if not raw:
                continue
            n = int(raw)
            lo = 0 if allow_zero else min_val
            if lo <= n <= max_val:
                return n
            print(f"  {C_RED}⚠ Nhập số từ {lo}–{max_val}{C_RESET}")
        except ValueError:
            print(f"  {C_RED}⚠ Nhập số hợp lệ{C_RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_DIM}Đã hủy.{C_RESET}")
            sys.exit(0)


def input_multi_choice(prompt: str, max_val: int) -> list[int]:
    """Nhập nhiều số, phân tách bởi dấu phẩy hoặc khoảng trắng."""
    while True:
        try:
            raw = input(f"\n{C_GREEN}▸ {prompt}: {C_RESET}").strip()
            if not raw:
                continue
            parts = raw.replace(",", " ").split()
            nums = []
            for p in parts:
                n = int(p)
                if 0 <= n <= max_val:
                    nums.append(n)
                else:
                    print(f"  {C_RED}⚠ {n} nằm ngoài khoảng 0–{max_val}{C_RESET}")
                    nums = []
                    break
            if nums:
                return nums
        except ValueError:
            print(f"  {C_RED}⚠ Nhập danh sách số cách nhau bằng dấu phẩy hoặc khoảng trắng{C_RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_DIM}Đã hủy.{C_RESET}")
            sys.exit(0)


def confirm(prompt: str, default_yes: bool = True) -> bool:
    hint = "Y/n" if default_yes else "y/N"
    try:
        raw = input(f"{C_GREEN}▸ {prompt} [{hint}]: {C_RESET}").strip().lower()
        if not raw:
            return default_yes
        return raw in ("y", "yes", "có", "co")
    except (KeyboardInterrupt, EOFError):
        return False


# ═══════════════════════════════════════════════════════════
#  Bước 1: Chọn chế độ (file / folder)
# ═══════════════════════════════════════════════════════════
def step_choose_mode() -> str:
    print_header("NORMALIZE DỮ LIỆU CRAWL")
    print_menu([
        "Xử lý 1 file",
        "Xử lý 1 folder",
    ])
    choice = input_choice("Chọn chế độ (1-2)", 2)
    return "file" if choice == 1 else "folder"


# ═══════════════════════════════════════════════════════════
#  Bước 2: Chọn folder
# ═══════════════════════════════════════════════════════════
def _list_folders(base_dir: Path) -> list[Path]:
    """Liệt kê folder con + chính nó nếu có file .md/.txt."""
    folders = []
    # Thêm chính base_dir nếu có file
    md_files = list(base_dir.glob("*.md")) + list(base_dir.glob("*.txt"))
    if md_files:
        folders.append(base_dir)
    # Thêm các folder con
    for d in sorted(base_dir.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and not d.name.startswith("__"):
            sub_files = list(d.glob("*.md")) + list(d.glob("*.txt"))
            if sub_files:
                folders.append(d)
    return folders


def step_choose_folder() -> Path:
    print_header("CHỌN FOLDER")

    # Hiển thị các folder có dữ liệu
    folders = _list_folders(DEFAULT_INPUT_DIR)

    if not folders:
        print(f"  {C_RED}Không tìm thấy folder chứa file .md/.txt trong {DEFAULT_INPUT_DIR}{C_RESET}")
        sys.exit(1)

    options = []
    for f in folders:
        rel = f.relative_to(PROJECT_DIR)
        count = len(list(f.glob("*.md")) + list(f.glob("*.txt")))
        options.append(f"{rel}/  {C_DIM}({count} files){C_RESET}")

    print_menu(options)
    choice = input_choice(f"Chọn folder (1-{len(folders)})", len(folders))
    selected = folders[choice - 1]
    print(f"  → {C_BOLD}{selected.relative_to(PROJECT_DIR)}/{C_RESET}")
    return selected


# ═══════════════════════════════════════════════════════════
#  Bước 3: Chọn file (nếu mode=file)
# ═══════════════════════════════════════════════════════════
def step_choose_file(folder: Path) -> Path:
    print_header("CHỌN FILE")

    files = sorted(
        [f for f in folder.iterdir()
         if f.is_file() and f.suffix in (".md", ".txt") and not f.name.startswith(".")],
        key=lambda f: f.name,
    )

    if not files:
        print(f"  {C_RED}Không có file .md/.txt trong {folder}{C_RESET}")
        sys.exit(1)

    # Hiện danh sách, rút gọn tên nếu dài
    options = []
    for f in files:
        name = f.name
        display = (name[:55] + "...") if len(name) > 58 else name
        size_kb = f.stat().st_size / 1024
        options.append(f"{display}  {C_DIM}({size_kb:.1f} KB){C_RESET}")

    print(f"  {C_DIM}Folder: {folder.relative_to(PROJECT_DIR)}/{C_RESET}")
    print_menu(options)
    choice = input_choice(f"Chọn file (1-{len(files)})", len(files))
    selected = files[choice - 1]
    print(f"  → {C_BOLD}{selected.name}{C_RESET}")
    return selected


# ═══════════════════════════════════════════════════════════
#  Bước 4: Chọn các bước xử lý
# ═══════════════════════════════════════════════════════════
def step_choose_processors() -> list[str]:
    print_header("CHỌN BƯỚC XỬ LÝ")
    print(f"  {C_DIM}Nhập nhiều số cách nhau bằng dấu phẩy hoặc khoảng trắng{C_RESET}")
    print(f"  {C_DIM}Ví dụ: 1,3,5  hoặc  0 (= tất cả){C_RESET}")
    print()

    # Option 0 = ALL
    print(f"  {C_YELLOW}[0]{C_RESET} {C_BOLD}✦ Tất cả (ALL){C_RESET}")
    for i, key in enumerate(PROCESSOR_KEYS, 1):
        proc = PROCESSORS[key]
        print(f"  {C_YELLOW}[{i}]{C_RESET} {proc['name']}")
        print(f"      {C_DIM}{proc['desc']}{C_RESET}")

    choices = input_multi_choice(
        f"Chọn bước xử lý (0=all, 1-{len(PROCESSOR_KEYS)})", len(PROCESSOR_KEYS)
    )

    if 0 in choices:
        selected = PROCESSOR_KEYS[:]
    else:
        selected = [PROCESSOR_KEYS[c - 1] for c in choices if 1 <= c <= len(PROCESSOR_KEYS)]
        # Loại trùng, giữ thứ tự pipeline
        seen = set()
        ordered = []
        for key in PROCESSOR_KEYS:
            if key in selected and key not in seen:
                ordered.append(key)
                seen.add(key)
        selected = ordered

    print(f"\n  Sẽ xử lý: {C_BOLD}{', '.join(selected)}{C_RESET}")
    return selected


# ═══════════════════════════════════════════════════════════
#  Xử lý 1 file qua các bước đã chọn
# ═══════════════════════════════════════════════════════════
def process_single_file(
    filepath: Path,
    steps: list[str],
    output_dir: Path,
    hashes: dict,
) -> dict:
    """
    Xử lý 1 file qua các bước normalize đã chọn.
    Trả về: {"status": "ok"|"dup"|"err", "message": str, ...}
    """
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

    # ── meta: luôn chạy để tách header ──
    if "meta" in steps:
        content, source_url, source_title = norm_meta.extract_meta_header(content)

    # ── clean_content ──
    if "clean_content" in steps:
        content = norm_clean_content.clean_content(content)

    # ── clean_html ──
    if "clean_html" in steps:
        content = norm_clean_html.clean_html_and_special_chars(content)

    # ── tables ──
    if "tables" in steps:
        try:
            content = norm_tables.process_tables(content)
        except Exception as e:
            print(f"    {C_YELLOW}⚠ tables lỗi: {e}{C_RESET}")

    # ── metadata ──
    if "metadata" in steps:
        tags = norm_metadata.detect_metadata_tags(content)
        year = norm_metadata.detect_year(content)

    # ── dedup ──
    if "dedup" in steps:
        doc_hash = norm_dedup.content_hash(content)
        if doc_hash in hashes and hashes[doc_hash] != filename:
            return {
                "status": "dup",
                "message": f"trùng với {hashes[doc_hash]}",
                "hash": doc_hash,
            }
        hashes[doc_hash] = filename
    else:
        doc_hash = norm_dedup.content_hash(content)

    # ── synonyms ──
    if "synonyms" in steps:
        content = norm_synonyms.expand_synonyms(content)

    # ── school ──
    school = norm_meta.extract_school(filename)

    # ── Ghi file output ──
    output_dir.mkdir(parents=True, exist_ok=True)
    out_lines = []

    if "meta" in steps:
        out_lines += [
            "[TITLE]",
            source_title or filename,
            "",
            "[URL]",
            source_url,
            "",
        ]

    if "metadata" in steps or "dedup" in steps:
        out_lines += [
            "[META]",
            f"school: {school}",
            f"tags: {','.join(tags)}",
            f"year: {year or ''}",
            f"hash: {doc_hash}",
            "",
        ]

    if out_lines:
        out_lines += ["---", ""]

    out_lines.append(content)
    out_content = "\n".join(out_lines)

    out_path = output_dir / filename
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_content)

    return {
        "status": "ok",
        "message": f"→ {out_path.relative_to(PROJECT_DIR)}",
        "tags": tags[:4],
        "year": year,
        "hash": doc_hash[:8],
        "chars": len(content),
    }


# ═══════════════════════════════════════════════════════════
#  Xử lý chính
# ═══════════════════════════════════════════════════════════
def load_hashes() -> dict:
    if HASH_FILE.exists():
        try:
            return json.loads(HASH_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_hashes(hashes: dict):
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HASH_FILE.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")


def run():
    # 1. Chọn mode
    mode = step_choose_mode()

    # 2. Chọn folder
    folder = step_choose_folder()

    # 3. Chọn file (nếu mode=file)
    if mode == "file":
        target_file = step_choose_file(folder)
        files = [target_file]
    else:
        files = sorted(
            [f for f in folder.iterdir()
             if f.is_file() and f.suffix in (".md", ".txt") and not f.name.startswith(".")],
            key=lambda f: f.name,
        )
        print(f"\n  → Sẽ xử lý {C_BOLD}{len(files)}{C_RESET} file trong {folder.relative_to(PROJECT_DIR)}/")

    # 4. Chọn bước xử lý
    steps = step_choose_processors()

    # 5. Xác nhận
    print_header("XÁC NHẬN")
    print(f"  Mode:    {C_BOLD}{'1 file' if mode == 'file' else 'folder'}{C_RESET}")
    print(f"  Files:   {C_BOLD}{len(files)}{C_RESET}")
    print(f"  Steps:   {C_BOLD}{', '.join(steps)}{C_RESET}")
    print(f"  Output:  {C_BOLD}{DEFAULT_OUTPUT_DIR.relative_to(PROJECT_DIR)}/{C_RESET}")

    if not confirm("\nBắt đầu xử lý?"):
        print(f"{C_DIM}Đã hủy.{C_RESET}")
        return

    # 6. Chạy
    print_header("ĐANG XỬ LÝ")

    hashes = load_hashes() if "dedup" in steps else {}
    stats = {"ok": 0, "dup": 0, "err": 0}

    for i, filepath in enumerate(files, 1):
        name = filepath.name
        short = (name[:50] + "...") if len(name) > 53 else name
        print(f"  [{i}/{len(files)}] {short}", end="  ")

        try:
            result = process_single_file(filepath, steps, DEFAULT_OUTPUT_DIR, hashes)
            status = result["status"]
            stats[status] += 1

            if status == "ok":
                info_parts = []
                if result.get("tags"):
                    info_parts.append(f"tags:{result['tags']}")
                if result.get("year"):
                    info_parts.append(f"y:{result['year']}")
                info_parts.append(f"{result['chars']} chars")
                info = " | ".join(info_parts)
                print(f"{C_GREEN}OK{C_RESET}  {C_DIM}{info}{C_RESET}")
            elif status == "dup":
                print(f"{C_YELLOW}DUP{C_RESET}  {C_DIM}{result['message']}{C_RESET}")
            else:
                print(f"{C_RED}ERR{C_RESET}  {result['message']}")

        except Exception as e:
            stats["err"] += 1
            print(f"{C_RED}ERR{C_RESET}  {e}")

    # Lưu hashes
    if "dedup" in steps:
        save_hashes(hashes)

    # 7. Tổng kết
    print_header("KẾT QUẢ")
    total = stats["ok"] + stats["dup"] + stats["err"]
    print(f"  Tổng:      {C_BOLD}{total}{C_RESET} file")
    print(f"  Thành công: {C_GREEN}{stats['ok']}{C_RESET}")
    if stats["dup"]:
        print(f"  Trùng lặp:  {C_YELLOW}{stats['dup']}{C_RESET}")
    if stats["err"]:
        print(f"  Lỗi:        {C_RED}{stats['err']}{C_RESET}")
    print(f"  Output:     {C_BOLD}{DEFAULT_OUTPUT_DIR.relative_to(PROJECT_DIR)}/{C_RESET}")
    print()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print(f"\n{C_DIM}Đã hủy.{C_RESET}")
