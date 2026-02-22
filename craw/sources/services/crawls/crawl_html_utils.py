#!/usr/bin/env python3
"""
Tiện ích crawl và xử lý trang HTML.
- Trích xuất text, bảng, ảnh, link file từ HTML
- OCR ảnh bảng trong HTML
"""
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urlparse, urljoin
import os

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DOWNLOADABLE_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}


def extract_file_links_from_html(html: str, base_url: str) -> set[str]:
    """Trích xuất link file (PDF, Word, Excel...) từ HTML để tải về."""
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full_url = urljoin(base_url, href).split("#")[0].split("?")[0]
        ext = os.path.splitext(urlparse(full_url).path)[1].lower()
        if ext in DOWNLOADABLE_EXTENSIONS:
            found.add(full_url)
    return found


def ocr_images_in_soup(soup, base_url: str):
    """OCR ảnh trong soup: bảng điểm hoặc ảnh chứa text/bảng."""
    try:
        from ocr_image_table import ocr_table_from_image_url, ocr_generic_text_from_image_url
    except ImportError:
        return

    OCR_MIN_BYTES = 5_000
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src") or img_tag.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        full_src = urljoin(base_url, src)
        ext = os.path.splitext(urlparse(full_src).path)[1].lower()
        if ext in (".svg", ".gif", ".ico", ".webp"):
            continue
        try:
            head = requests.head(full_src, headers=HEADERS, timeout=10, allow_redirects=True)
            size = int(head.headers.get("Content-Length", 0) or 0)
            if size and size < OCR_MIN_BYTES:
                continue
        except Exception:
            pass

        ocr_text = None
        try:
            ocr_text = ocr_table_from_image_url(full_src, verbose=False)
            if not ocr_text or len(ocr_text.strip()) < 30:
                ocr_text = ocr_generic_text_from_image_url(full_src, verbose=False)
        except Exception:
            try:
                ocr_text = ocr_generic_text_from_image_url(full_src, verbose=False)
            except Exception:
                pass

        if ocr_text and len(ocr_text.strip()) > 20:
            img_tag.name = "p"
            img_tag.attrs = {}
            img_tag.string = ocr_text


def html_to_text(html: str, url: str) -> tuple[str | None, str]:
    """Chuyển HTML sang text (markdown), bao gồm bảng. Trả về (text, title)."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""

    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
        tag.decompose()

    CONTENT_SELECTORS = [
        "article", "main", "[class*='entry-content']", "[class*='post-content']",
        "[class*='content-area']", "[class*='article-body']", "[class*='page-content']",
    ]
    content_node = None
    for sel in CONTENT_SELECTORS:
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 150:
            content_node = node
            break
    work_soup = content_node if content_node else soup

    ocr_images_in_soup(work_soup, url)

    for img in work_soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src and not src.startswith("data:"):
            img["src"] = urljoin(url, src)

    try:
        text = md(str(work_soup), heading_style="ATX")
    except Exception:
        text = work_soup.get_text(separator="\n")

    lines = [l.strip() for l in text.splitlines()]
    cleaned = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False
    return "\n".join(cleaned).strip(), title


def crawl_html_page(url: str, timeout: int = 15) -> tuple[str | None, list[str]]:
    """Crawl trang HTML. Trả về (text, file_urls)."""
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    if ext in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".mp4", ".jpg", ".png"}:
        return None, []

    html = None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            html = resp.text
    except Exception:
        pass

    if not html:
        return None, []

    file_urls = list(extract_file_links_from_html(html, url))
    text, title = html_to_text(html, url)
    if not text or len(text) < 150:
        return None, file_urls

    meta = f"[{title}]\n" if title else ""
    return f"{meta}[URL: {url}]\n\n{text}", file_urls
