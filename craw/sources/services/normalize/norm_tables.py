#!/usr/bin/env python3
"""Chuẩn hóa bảng biểu (Markdown tables).

Mục tiêu: chuyển bảng Markdown sang dạng văn bản mô tả ngữ nghĩa để embedding
hiểu rõ cấu trúc (cột -> giá trị) và hạn chế mất dữ liệu.

Lưu ý: nhiều bảng thực tế có số cột không đều (do merge cell, thiếu pipe,...)
nên không thể chỉ giữ các row khớp đúng số cột.
"""

from __future__ import annotations

import re


# Match a Markdown table block consisting of 2+ consecutive lines starting with '|'.
# Must also match when the last row is at EOF without a trailing newline.
_TABLE_BLOCK_RE = re.compile(
    r"(?m)(^|\n)([\t ]*\|[^\n]*(?:\n[\t ]*\|[^\n]*)+)(?=\n|$)",
)


def _is_separator_row(line: str) -> bool:
    """Detect Markdown separator row like: | --- | :---: | ---: |"""
    s = line.strip().strip("|").strip()
    if not s:
        return False
    # allow : for alignment
    return all(re.fullmatch(r":?-{3,}:?", part.strip()) for part in s.split("|"))


def _split_cells(line: str) -> list[str]:
    # Basic split for Markdown table row.
    return [c.strip() for c in line.strip().strip("|").split("|")]


def md_table_to_text(md_table: str) -> str:
    """Convert one Markdown table block to semantic text.

    Output format (each row one line):
      "Header1: value1, Header2: value2, ..."
    """
    raw_lines = [l.rstrip() for l in md_table.splitlines()]
    lines = [l.strip() for l in raw_lines if l.strip()]
    if not lines:
        return md_table
    if not any("|" in l for l in lines):
        return md_table

    header: list[str] | None = None
    rows: list[list[str]] = []

    for line in lines:
        if "|" not in line:
            continue
        if _is_separator_row(line):
            continue
        cells = _split_cells(line)
        if header is None:
            # Some tables start with an empty header row like: | | | |
            # Skip it and use the next meaningful row as header.
            if all(c == "" for c in cells):
                continue

            header = cells
            # Drop trailing/leading empty headers caused by stray pipes
            while header and header[0] == "":
                header.pop(0)
            while header and header[-1] == "":
                header.pop()

            # If header became empty after trimming, keep searching.
            if not header or all(h.strip() == "" for h in header):
                header = None
                continue
            continue
        rows.append(cells)

    if not header:
        return md_table

    # Normalize row widths (pad / merge extras) to avoid dropping content.
    norm_rows: list[list[str]] = []
    for row in rows:
        # Trim empties caused by stray leading/trailing pipes
        while row and row[0] == "":
            row.pop(0)
        while row and row[-1] == "":
            row.pop()

        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        elif len(row) > len(header):
            # Merge extra cells into the last column
            merged_last = "; ".join([c for c in row[len(header) - 1 :] if c])
            row = row[: len(header) - 1] + [merged_last]
        norm_rows.append(row)

    sentences: list[str] = []
    for row in norm_rows:
        pairs = []
        for h, v in zip(header, row):
            h2 = (h or "").strip()
            v2 = (v or "").strip()

            # Common placeholder in PTIT admission tables
            if v2.upper() == "X":
                v2 = "không có dữ liệu"

            # Many scraped tables encode multiple sub-fields inside a single cell using '|'
            # (e.g. "– | – | – | –"). This is confusing for embedding/search, so normalize
            # it into a clearer delimiter.
            if "|" in v2:
                v2 = re.sub(r"\s*\|\s*", "; ", v2)
                v2 = re.sub(r"\s{2,}", " ", v2).strip(" ;")
            if not h2 and not v2:
                continue
            if not h2:
                h2 = "field"
            pairs.append(f"{h2}: {v2}")
        if pairs:
            sentences.append(", ".join(pairs))

    return "\n".join(sentences) if sentences else md_table


def normalize_tables_in_content(text: str) -> str:
    """Find Markdown tables and convert them to semantic text."""

    def replacer(match: re.Match) -> str:
        prefix = match.group(1) or ""
        md_table = match.group(2) or ""
        converted = md_table_to_text(md_table)
        # Keep the original prefix (start-of-file or '\n') and ensure the
        # converted block ends with a newline so the next content stays separated.
        return f"{prefix}{converted}\n"

    return _TABLE_BLOCK_RE.sub(replacer, text or "")


def process_tables(text: str) -> str:
    """Public entrypoint."""
    return normalize_tables_in_content(text)
