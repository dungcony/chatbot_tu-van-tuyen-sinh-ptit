#!/usr/bin/env python3
"""crawl_hierarchical.py

Crawl link từ một URL gốc.

Mục tiêu chính:
- Thu thập danh sách URL (không crawl nội dung).
- Có thể lưu danh sách này thành JSON trong `public/links/` để dùng với
    `run_crawl_from_links.py` (crawl nội dung hàng loạt).

Các chế độ scope:
- path (mặc định): chỉ lấy URL cùng domain và cùng prefix path với base_url.
- domain: lấy URL cùng domain (không giới hạn path) (cẩn thận vì có thể rất nhiều).
- page: chỉ lấy link ngay trên trang base_url (không BFS sang trang con).
"""
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

SKIP_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp",
    ".mp4", ".avi", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".woff", ".woff2",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _normalize_url(url: str) -> str:
    """Chuẩn hóa URL: bỏ fragment, query, trailing slash."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _is_under_path(url: str, base_path: str) -> bool:
    """
    Kiểm tra URL có nằm dưới base_path không.
    base_path: /tin  -> match /tin, /tin/page1, /tin/2025/bai-viet
    base_path: /tin/  -> tương tự
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    base = base_path.rstrip("/") or "/"
    if not base.startswith("/"):
        base = "/" + base
    return path == base or path.startswith(base + "/")


# Cụm từ nhận diện trang 404 (soft 404 - server trả 200 nhưng nội dung lỗi)
ERROR_404_PATTERNS = [
    "không tìm thấy trang", "page not found", "lỗi 404", "error 404",
    "trang không tồn tại", "trang bạn tìm kiếm không tồn tại",
]


def _fetch_sitemap_urls(base_url: str, base_path: str, timeout: int = 10) -> set[str]:
    """
    Lấy URLs từ sitemap (sitemap.xml, wp-sitemap.xml, robots.txt).
    Trả về các URL nằm dưới base_path.
    """
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "https"
    base_origin = f"{scheme}://{parsed.netloc}"
    found = set()

    def fetch_xml(url: str) -> str | None:
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        return None

    def extract_locs(xml_text: str) -> list[str]:
        urls = []
        try:
            root = ET.fromstring(xml_text)
            for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if loc.text:
                    urls.append(loc.text.strip())
            if not urls:
                for loc in root.iter("loc"):
                    if loc.text:
                        urls.append(loc.text.strip())
        except ET.ParseError:
            pass
        return urls

    sitemap_candidates = [
        f"{base_origin}/wp-sitemap.xml",
        f"{base_origin}/sitemap.xml",
        f"{base_origin}/sitemap_index.xml",
    ]
    try:
        r = requests.get(f"{base_origin}/robots.txt", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            for line in r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_candidates.insert(0, line.split(":", 1)[1].strip())
    except Exception:
        pass

    to_fetch = []
    for url in sitemap_candidates:
        xml_text = fetch_xml(url)
        if not xml_text:
            continue
        locs = extract_locs(xml_text)
        for loc in locs:
            if loc.lower().endswith(".xml"):
                to_fetch.append(loc)
            elif _is_under_path(loc, base_path):
                found.add(_normalize_url(loc))
        if to_fetch:
            break

    for sitemap_url in to_fetch[:25]:
        xml_text = fetch_xml(sitemap_url)
        if not xml_text:
            continue
        for loc in extract_locs(xml_text):
            if not loc.lower().endswith(".xml") and _is_under_path(loc, base_path):
                found.add(_normalize_url(loc))
        time.sleep(0.2)

    return found


def _url_exists(url: str, timeout: int = 5) -> bool:
    """Kiểm tra URL có tồn tại không (HEAD request, loại 404)."""
    try:
        resp = requests.head(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return resp.status_code < 400
    except Exception:
        return False


def _fetch_html(url: str, timeout: int = 15, use_playwright: bool = True) -> str | None:
    """Lấy HTML từ URL."""
    if use_playwright and _PLAYWRIGHT_AVAILABLE:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
                return html
        except Exception:
            pass
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def _extract_links(html: str, base_url: str, base_path: str, *, scope: str = "path") -> set[str]:
    """Trích xuất các link.

    scope:
      - path: cùng domain + dưới base_path
      - domain: cùng domain
      - page: cùng domain (không ràng buộc path; BFS được xử lý ở caller)
    """
    soup = BeautifulSoup(html, "html.parser")
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()
    found = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        full_url = urljoin(base_url, href).split("#")[0].split("?")[0].rstrip("/")
        if not full_url:
            continue
        parsed = urlparse(full_url)
        if parsed.netloc.lower() != base_domain:
            continue
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext in SKIP_EXTENSIONS:
            continue
        if scope == "path":
            if not _is_under_path(full_url, base_path):
                continue
        elif scope in ("domain", "page"):
            pass
        else:
            # fallback an toàn
            if not _is_under_path(full_url, base_path):
                continue

        norm = _normalize_url(full_url)
        if norm != _normalize_url(base_url):
            found.add(norm)
    return found


def crawl_hierarchical(
    base_url: str,
    max_pages: int = 500,
    use_playwright: bool = True,
    delay_seconds: float = 1.0,
    validate_urls: bool = True,
    use_sitemap: bool = True,
    verbose: bool = True,
    scope: str = "path",
) -> list[str]:
    """
    Crawl toàn bộ link phân cấp dưới base_url.

    Ví dụ:
        base_url = "https://tuyensinh.ptit.edu.vn/tin-tuc"
        -> Trả về: [
            "https://tuyensinh.ptit.edu.vn/tin-tuc",
            "https://tuyensinh.ptit.edu.vn/tin-tuc/page/2",
            "https://tuyensinh.ptit.edu.vn/tin-tuc/2025/bai-viet-xyz",
            ...
        ]

    Args:
        base_url: URL gốc (vd: https://site.com/tin)
        max_pages: Số trang tối đa
        use_playwright: Dùng Playwright nếu có (trang load bằng JS)
        delay_seconds: Thời gian chờ giữa các request
        validate_urls: Kiểm tra URL tồn tại (HEAD) trước khi thêm, loại bỏ 404
        use_sitemap: Lấy thêm URLs từ sitemap (sitemap.xml, wp-sitemap.xml) - tìm được nhiều bài viết hơn
        verbose: In log

    Returns:
        Danh sách URL đã tìm thấy (đã chuẩn hóa, sắp xếp)
    """
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/") or "/"

    # Đảm bảo base_url cũng nằm trong kết quả
    all_urls = {_normalize_url(base_url)}
    queue = deque([base_url])
    visited = set()

    # page-scope: chỉ extract link ngay trên base_url (không BFS)
    if scope == "page":
        html = _fetch_html(base_url, use_playwright=use_playwright)
        if not html:
            return sorted(all_urls)
        html_lower = html[:3000].lower()
        if any(p in html_lower for p in ERROR_404_PATTERNS):
            return sorted(all_urls)
        links = _extract_links(html, base_url, base_path, scope="page")
        for link in links:
            if link not in all_urls:
                if validate_urls and not _url_exists(link):
                    continue
                all_urls.add(link)
                if len(all_urls) >= max_pages:
                    break
        result = sorted(all_urls)
        if verbose:
            print(f"\nTổng: {len(result)} URL")
        return result

    # Lấy URLs từ sitemap trước (tìm được bài viết mà HTML không có link)
    # Chỉ chạy sitemap khi scope != page
    if use_sitemap:
        sitemap_urls = _fetch_sitemap_urls(base_url, base_path)
        if sitemap_urls:
            added = 0
            for u in sitemap_urls:
                if len(all_urls) >= max_pages:
                    break
                if u not in all_urls:
                    if validate_urls and not _url_exists(u):
                        if verbose:
                            print(f"    SKIP (404): {u}")
                        continue
                    all_urls.add(u)
                    queue.append(u)
                    added += 1
            if verbose and added:
                print(f"  [Sitemap] +{added} URL (max={max_pages})")

    while queue and len(all_urls) < max_pages:
        url = queue.popleft()
        norm = _normalize_url(url)
        if norm in visited:
            continue
        visited.add(norm)

        if verbose:
            print(f"  [{len(all_urls)}] {url}")

        html = _fetch_html(url, use_playwright=use_playwright)
        if not html:
            continue

        # Bỏ qua trang 404 (soft 404 - server trả 200 nhưng nội dung lỗi)
        html_lower = html[:3000].lower()
        if any(p in html_lower for p in ERROR_404_PATTERNS):
            if verbose:
                print(f"    SKIP (404): {url}")
            continue

        links = _extract_links(html, url, base_path, scope=scope)
        for link in links:
            if link not in all_urls:
                if validate_urls and not _url_exists(link):
                    if verbose:
                        print(f"    SKIP (404): {link}")
                    continue
                all_urls.add(link)
                if len(all_urls) >= max_pages:
                    break
                queue.append(link)

        time.sleep(delay_seconds)

    result = sorted(all_urls)
    if verbose:
        print(f"\nTổng: {len(result)} URL")
    return result


# --- CLI ---
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Crawl link phân cấp từ URL gốc")
    ap.add_argument("url", help="URL gốc (vd: https://tuyensinh.ptit.edu.vn/tin-tuc)")
    ap.add_argument("--max", "-m", type=int, default=500, help="Số URL tối đa")
    ap.add_argument("--no-playwright", action="store_true", help="Không dùng Playwright")
    ap.add_argument("--delay", "-d", type=float, default=1.0, help="Giây chờ giữa các request")
    ap.add_argument("--output", "-o", help="Lưu danh sách URL ra file (mỗi dòng 1 URL)")
    ap.add_argument("-q", "--quiet", action="store_true", help="Không in log")
    ap.add_argument("--no-validate", action="store_true", help="Không kiểm tra 404 (nhanh hơn nhưng có thể có link lỗi)")
    ap.add_argument("--no-sitemap", action="store_true", help="Không dùng sitemap")
    ap.add_argument(
        "--scope",
        choices=["path", "domain", "page"],
        default="path",
        help="Phạm vi lấy link: path (mặc định), domain (cùng domain), page (chỉ 1 trang)",
    )
    ap.add_argument(
        "--save-links",
        action="store_true",
        help="Lưu danh sách URL thành JSON trong public/links/ để crawl theo file JSON",
    )
    args = ap.parse_args()

    urls = crawl_hierarchical(
        base_url=args.url,
        max_pages=args.max,
        use_playwright=not args.no_playwright,
        delay_seconds=args.delay,
        validate_urls=not args.no_validate,
        use_sitemap=not args.no_sitemap,
        verbose=not args.quiet,
        scope=args.scope,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(urls))
        print(f"Đã lưu {len(urls)} URL vào {args.output}")

    # Luôn tạo file JSON log trong folder scripts: ex_{tên_link}.json
    parsed = urlparse(args.url)
    slug = re.sub(r"[^\w\-]", "_", f"{parsed.netloc}_{parsed.path}".strip("/_"))[:80]
    json_path = Path(__file__).resolve().parent / f"ex_{slug}.json"
    json_data = {
        "base_url": args.url,
        "urls": urls,
        "count": len(urls),
        "scope": args.scope,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu JSON: {json_path}")

    # Tuỳ chọn: lưu JSON trong public/links/ đúng format để run_crawl_from_links đọc
    if args.save_links:
        root = Path(__file__).resolve().parent.parent.parent
        links_dir = root / "public" / "links"
        links_dir.mkdir(parents=True, exist_ok=True)
        links_json_path = links_dir / f"{slug}.json"
        # Format: dict -> list URL string (flatten_links_from_json sẽ đọc được)
        links_data = {
            "meta": {
                "base_url": args.url,
                "scope": args.scope,
                "count": len(urls),
            },
            "urls": urls,
        }
        with open(links_json_path, "w", encoding="utf-8") as f:
            json.dump(links_data, f, ensure_ascii=False, indent=2)
        print(f"Đã lưu links JSON: {links_json_path}")

    if not args.output:
        for u in urls:
            print(u)
