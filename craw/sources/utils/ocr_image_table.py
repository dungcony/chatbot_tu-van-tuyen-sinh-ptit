import sys, os, re, io, math, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageEnhance
import easyocr

# ─────────────────────────── cau hinh ───────────────────────────
ROW_GAP_RATIO   = 0.020   # ty le chieu cao anh de phân biet 2 hang khác nhau
OCR_MIN_BYTES   = 50_000  # bo qua anh < 50 KB (icon, avatar)
MERGE_X_RATIO   = 1.2     # nhan voi chieu cao token de gop token lien ke (cung tu)

RE_MA_NGANH       = re.compile(r'^\d{7}$')          # khop chinh xac 1 ma nganh
RE_MA_NGANH_FIND  = re.compile(r'\b\d{7}\b')       # tim ma nganh trong chuoi bat ky
RE_SCORE          = re.compile(r'^\d{1,3}([.,]\d{1,2})?$')
RE_SCORE_FIND     = re.compile(r'\b\d{1,3}[.,]\d{1,4}\b')

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}

_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        print("  [OCR] Khoi tao EasyOCR reader...")
        _reader = easyocr.Reader(['vi', 'en'], gpu=False, verbose=False)
    return _reader


# ─────────────────────── tien xu ly anh ────────────────────────
def _preprocess(img_bytes: bytes) -> bytes:
    """Grayscale + tang tuong phan x2 + scale 2x -> PNG bytes."""
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ──────────────────── OCR -> hang (rows) ───────────────────────
def _ocr_to_rows(img_bytes: bytes, verbose: bool = False):
    """
    Chay EasyOCR detail=1 tren anh da tien xu ly.
    Sap xep token theo center_y, gom nhom thanh hang dua tren ROW_GAP_RATIO.
    Tra ve list of rows, moi row la list of (x_center, text).
    """
    img = Image.open(io.BytesIO(img_bytes))
    img_w, img_h = img.size
    gap = ROW_GAP_RATIO * img_h
    if verbose:
        print(f"      [OCR-dbg] Kich thuoc anh da xu ly: {img_w}x{img_h}px, gap={gap:.1f}px")

    reader = _get_reader()
    result = reader.readtext(img_bytes, detail=1, paragraph=False)
    if verbose:
        print(f"      [OCR-dbg] EasyOCR raw tokens: {len(result)}")
        for bbox, text, conf in result[:10]:
            ys = [p[1] for p in bbox]
            xs = [p[0] for p in bbox]
            print(f"        cy={sum(ys)/len(ys):.0f} cx={sum(xs)/len(xs):.0f} conf={conf:.2f} '{text}'")
        if len(result) > 10:
            print(f"        ... va {len(result)-10} token khac")

    # Moi phan tu: (bbox, text, conf)
    # bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    tokens = []
    for bbox, text, conf in result:
        text = text.strip()
        if not text:
            continue
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        h  = max(ys) - min(ys)
        tokens.append((cy, cx, h, text))

    tokens.sort(key=lambda t: t[0])  # sap xep theo center_y

    rows = []
    cur_row = []
    cur_y   = None

    for cy, cx, th, text in tokens:
        if cur_y is None or abs(cy - cur_y) <= gap:
            cur_row.append((cx, th, text))
            cur_y = cy if cur_y is None else (cur_y + cy) / 2
        else:
            if cur_row:
                rows.append(sorted(cur_row, key=lambda t: t[0]))
            cur_row = [(cx, th, text)]
            cur_y   = cy

    if cur_row:
        rows.append(sorted(cur_row, key=lambda t: t[0]))

    if verbose:
        print(f"      [OCR-dbg] Gruop thanh {len(rows)} hang")

    return rows


# ──────────────────── gop token trong hang ─────────────────────
def _merge_row_tokens(row):
    """
    Gop cac token lien ke (khoang cach x < MERGE_X_RATIO * token_height)
    -> list of (x_center, merged_text)
    """
    if not row:
        return []
    merged = []
    cx0, th0, txt0 = row[0]
    x_end = cx0 + th0 * MERGE_X_RATIO   # uoc tinh diem ket thuc

    for cx, th, txt in row[1:]:
        if cx - x_end < MERGE_X_RATIO * th0:
            txt0 = txt0 + " " + txt
            x_end = cx + th * MERGE_X_RATIO
        else:
            merged.append((cx0, txt0))
            cx0, th0, txt0 = cx, th, txt
            x_end = cx + th * MERGE_X_RATIO

    merged.append((cx0, txt0))
    return merged


# ─────────────────── parse 1 hang du lieu ──────────────────────
def _parse_data_row(cells, verbose: bool = False):
    """
    Tim ma nganh (7 chu so) trong cells, lay ten nganh va 9 diem.
    Xu ly ca truong hop 1 cell chua NHIEU ma nganh (nhieu nganh tren cung hang anh).
    Tra ve LIST of dict (co the nhieu hon 1 dong neu image pack nhieu nganh/hang).
    """
    # Tim cell dau tien chua it nhat 1 ma nganh 7 chu so
    ma_cell_idx = None
    ma_list     = []
    for i, (_, txt) in enumerate(cells):
        found = RE_MA_NGANH_FIND.findall(txt)
        if found:
            ma_cell_idx = i
            ma_list = found
            break

    if ma_cell_idx is None:
        if verbose:
            cell_texts = [t for _, t in cells]
            print(f"        [OCR-dbg] SKIP hang (khong co ma nganh 7-so): {cell_texts}")
        return []

    n = len(ma_list)  # so nganh trong hang nay

    # Lay cac cot diem (cells sau cot ma nganh)
    # Moi cot diem nen co dung n gia tri (1 per nganh)
    score_cols = []
    for j in range(ma_cell_idx + 1, len(cells)):
        _, txt = cells[j]
        vals = txt.replace(",", ".").split()
        clean_vals = []
        for v in vals:
            v2 = v.strip()
            if RE_SCORE.match(v2.replace(",", ".")):
                clean_vals.append(v2.replace(",", "."))
            elif v2 in ("-", "–", "—", "x", "X", ""):
                clean_vals.append("-")
            else:
                # Loai bo cac chu nhu TTNV<=2, giu so truoc no
                m = re.match(r'^(\d{1,3}[.,]?\d*)(.*)$', v2)
                if m:
                    clean_vals.append(m.group(1).replace(",", "."))
                else:
                    clean_vals.append(v2)
        if clean_vals:
            score_cols.append(clean_vals)

    if verbose:
        print(f"        [OCR-dbg] ma_list={ma_list}, n={n}, score_cols={len(score_cols)}")
        for ci, col in enumerate(score_cols):
            print(f"          col[{ci}]: {col}")

    # Tao 1 row per nganh, lay gia tri thu k tu each cot diem
    result = []
    for k, ma in enumerate(ma_list):
        scores = []
        for col in score_cols:
            if k < len(col):
                scores.append(col[k])
            else:
                scores.append("-")
        while len(scores) < 9:
            scores.append("-")
        scores = scores[:9]
        result.append({
            "ten_nganh": "",   # ten nganh kho tach khi nhieu nganh on cung hang
            "ma_nganh":  ma,
            "scores":    scores,
        })

    if verbose:
        for r in result:
            print(f"        [OCR-dbg] -> ma={r['ma_nganh']} scores={r['scores']}")

    return result


# ─────────────────── tao bang markdown ─────────────────────────
HEADERS_MD = [
    "Ngành", "Mã ngành",
    "THPT", "ĐGNL/TSA", "SAT", "ACT", "HSA", "SPT", "APT", "Kết hợp", "TTNV"
]

def _rows_to_markdown(data_rows, section_title=""):
    if not data_rows:
        return ""
    lines = []
    if section_title:
        lines.append(f"\n## {section_title}\n")
    lines.append("| " + " | ".join(HEADERS_MD) + " |")
    lines.append("|" + "|".join(["---"] * len(HEADERS_MD)) + "|")
    for row in data_rows:
        cols = [row["ten_nganh"], row["ma_nganh"]] + row["scores"]
        lines.append("| " + " | ".join(cols) + " |")
    return "\n".join(lines)


# ──────────────── OCR generic: ảnh chứa text/bảng bất kỳ ───────
def ocr_generic_text_from_image_url(img_url: str, verbose: bool = False) -> str:
    """
    OCR ảnh lấy text (bảng hoặc text thường). Dùng khi ocr_table_from_image_url
    trả về rỗng (ảnh không phải bảng điểm chuẩn).
    Trả về markdown: bảng nếu có cấu trúc, hoặc đoạn text.
    """
    resp = requests.get(img_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    processed = _preprocess(resp.content)
    rows = _ocr_to_rows(processed, verbose=verbose)
    if not rows:
        return ""

    lines = []
    for row in rows:
        cells = _merge_row_tokens(row)
        cell_texts = [t.strip() for _, t in cells if t.strip()]
        if cell_texts:
            lines.append(" | ".join(cell_texts))

    if not lines:
        return ""
    text = "\n".join(lines)
    # Nếu có vẻ là bảng (nhiều cột, nhiều dòng): format markdown table
    if len(lines) >= 2 and " | " in lines[0]:
        parts = [l.split(" | ") for l in lines]
        col_count = len(parts[0])
        if col_count >= 2 and all(len(p) == col_count for p in parts[: min(10, len(parts))]):
            sep = "|" + "|".join(["---"] * col_count) + "|"
            rows_md = ["| " + " | ".join(p) + " |" for p in parts]
            return rows_md[0] + "\n" + sep + "\n" + "\n".join(rows_md[1:])
    return text


# ──────────────── public API: 1 URL anh ────────────────────────
def ocr_table_from_image_url(img_url: str, section_title: str = "", verbose: bool = False) -> str:
    """
    Download anh tu img_url, chay OCR bang-diem, tra ve markdown table.
    verbose=True: in log chi tiet tung hang de debug.
    """
    resp = requests.get(img_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    print(f"    [OCR] Download anh: {len(resp.content)//1024}KB, url=...{img_url[-60:]}")

    processed = _preprocess(resp.content)
    rows = _ocr_to_rows(processed, verbose=verbose)

    data_rows = []
    skipped = 0
    for i, row in enumerate(rows):
        cells = _merge_row_tokens(row)
        parsed_list = _parse_data_row(cells, verbose=verbose)
        if parsed_list:
            data_rows.extend(parsed_list)
            if verbose:
                for parsed in parsed_list:
                    print(f"        [OCR-dbg] -> Hang {i}: ma={parsed['ma_nganh']} scores={parsed['scores']}")
        else:
            skipped += 1

    print(f"    [OCR] Ket qua: {len(data_rows)} dong parse duoc, {skipped} hang bo qua")
    return _rows_to_markdown(data_rows, section_title)


# ──────────── public API: tim tat ca anh trong 1 trang ─────────
def ocr_page_tables(page_url: str):
    """
    Fetch trang HTML, tim cac <img> lon (>= OCR_MIN_BYTES qua HEAD),
    OCR tung anh, gop ket qua.
    Tra ve list of (img_url, markdown_table).
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse

    resp = requests.get(page_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        ext = os.path.splitext(urlparse(src).path)[1].lower()
        if ext in (".svg", ".gif", ".ico", ".webp"):
            continue
        full_src = urljoin(page_url, src)
        try:
            head = requests.head(full_src, headers=HEADERS, timeout=10, allow_redirects=True)
            size = int(head.headers.get("Content-Length", 0))
            if size and size < OCR_MIN_BYTES:
                continue
        except Exception:
            pass   # neu khong biet size thi van thu OCR
        try:
            md_table = ocr_table_from_image_url(full_src)
            if md_table and len(md_table.strip()) > 30:
                results.append((full_src, md_table))
        except Exception as e:
            print(f"    WARN OCR loi {full_src[-50:]}: {e}")

    return results


# ────────────── public API: OCR va luu file markdown ───────────
def ocr_and_save(
    page_url: str,
    school_id: str,
    output_path: str,
    page_title: str = "",
    extra_text: str = "",
) -> dict:
    """
    OCR toan bo anh tren page_url, gop markdown, luu ra output_path.
    Tra ve {"rows": int, "output": str}.
    """
    tables = ocr_page_tables(page_url)
    if not tables:
        return {"rows": 0, "output": ""}

    all_md = []
    total_rows = 0
    for img_url, md_table in tables:
        all_md.append(md_table)
        total_rows += md_table.count("\n| ")

    title_line = page_title or page_url
    header = f"[{title_line}]\n[URL: {page_url}]\n\n# {title_line}\n"
    if extra_text:
        header += f"\n{extra_text}\n"

    content = header + "\n\n".join(all_md) + "\n"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  [OCR] Luu {total_rows} dong -> {output_path}")
    return {"rows": total_rows, "output": output_path}


# ─────────────────────────── CLI ───────────────────────────────
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="OCR bang diem chuan tu anh tren web")
    ap.add_argument("--url",    required=True, help="URL trang chua anh bang diem")
    ap.add_argument("--school", required=True, help="school_id (vd: ptit)")
    ap.add_argument("--output", default="", help="Duong dan file .md dau ra")
    ap.add_argument("--title",  default="", help="Tieu de trang")
    ap.add_argument("--embed",  action="store_true", help="Sau khi luu, chay embed vao MongoDB")
    args = ap.parse_args()

    if not args.output:
        slug = re.sub(r'[^\w-]', '-', args.url.split("//")[-1])[:60]
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        args.output = os.path.join(data_dir, f"{args.school}_{slug}.md")

    result = ocr_and_save(
        page_url   = args.url,
        school_id  = args.school,
        output_path= args.output,
        page_title = args.title,
    )

    if result["rows"] == 0:
        print("Khong tim duoc ban du lieu nao trong anh.")
    else:
        print(f"Thanh cong: {result['rows']} dong -> {result['output']}")

    if args.embed and result["rows"] > 0:
        from prepare_data import process_files
        chunks = process_files([result["output"]], school_id=args.school)
        print(f"Embed: {chunks} chunks vao MongoDB")
