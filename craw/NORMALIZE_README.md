# Pipeline chuẩn hóa dữ liệu crawl

Flow: **Crawl** → **Normalize** → **Embed**

## Cấu trúc thư mục `normalize/`

Mỗi file xử lý 1 trường hợp, `run_normalize.py` đưa từng file .md qua theo thứ tự:

| File | Trường hợp |
|------|------------|
| `norm_meta.py` | Tách [Title] [URL], extract school |
| `norm_clean_content.py` | Xóa menu nav, footer, dòng rác |
| `norm_clean_html.py` | HTML, &nbsp;, khoảng trắng |
| `norm_tables.py` | Bảng vỡ → textualization |
| `norm_metadata.py` | Tags (diem_chuan, hoc_phi...), year |
| `norm_dedup.py` | Hash nội dung (dedup) |
| `norm_synonyms.py` | HSA, SAT, ACT... → giải thích |

## 1. Crawl (đã có)
```bash
python run_crawl.py
# hoặc
python run_crawl_from_links.py
```
→ Dữ liệu lưu vào `data/`

## 2. Normalize (chuẩn hóa)
```bash
python run_normalize.py
```
→ Dữ liệu đã xử lý lưu vào `nor/`

### Các bước xử lý (7 vấn đề theo Gemini)
| # | Vấn đề | Xử lý |
|---|--------|-------|
| 1 | HTML & ký tự đặc biệt | `clean_html_and_special_chars()` - xóa thẻ HTML, &nbsp;, chuẩn khoảng trắng |
| 2 | Bảng biểu vỡ | `table_normalizer` - textualization, gộp orphan, sửa typo |
| 3 | Chunking | Dùng trong prepare_data (RecursiveCharacterTextSplitter, overlap) |
| 4 | Links & metadata | Lưu source_url, source_title vào header file nor/ |
| 5 | Deduplication | Hash MD5 nội dung, bỏ qua file trùng |
| 6 | Metadata tags | Tự động gán: diem_chuan, hoc_phi, year... |
| 7 | Từ viết tắt | HSA→HSA (Đánh giá năng lực ĐHQGHN), SAT, ACT... |

### Tùy chọn
```bash
python run_normalize.py --file ptit_diem-chuan.md   # Chỉ 1 file
python run_normalize.py --no-synonym                # Không bổ sung từ đồng nghĩa
python run_normalize.py --no-dedup                  # Không bỏ qua file trùng
```

## 3. Embed (từ nor/)
```bash
USE_NOR=1 python -m prepare_data
```
→ Đọc từ `nor/`, chunk, embed lên MongoDB

Hoặc embed trực tiếp từ `data/` (bỏ qua bước 2):
```bash
python -m prepare_data
```
