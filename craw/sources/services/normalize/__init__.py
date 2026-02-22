"""
Pipeline chuẩn hóa: mỗi file xử lý 1 trường hợp.
Thứ tự: meta -> clean_content -> clean_html -> tables -> metadata -> dedup -> synonyms
"""
import logging
from dataclasses import dataclass
from typing import Optional

from . import norm_meta
from . import norm_clean_content
from . import norm_clean_html
from . import norm_tables
from . import norm_metadata
from . import norm_dedup
from . import norm_synonyms

logger = logging.getLogger(__name__)


@dataclass
class NormalizedDoc:
    """Kết quả chuẩn hóa 1 file."""
    content: str
    source_url: str
    source_title: str
    filename: str
    school: str
    tags: list[str]
    year: Optional[int]
    content_hash: str


def normalize_document(
    raw_text: str,
    filename: str,
    skip_synonyms: bool = False,
) -> NormalizedDoc:
    """
    Đưa nội dung qua từng processor theo thứ tự.
    """
    logger.debug("normalize_document: %s (raw %d chars)", filename, len(raw_text))

    content, source_url, source_title = norm_meta.extract_meta_header(raw_text)
    logger.debug("  meta: url=%s title=%s", source_url[:60] if source_url else "", source_title[:40] if source_title else "")

    content = norm_clean_content.clean_content(content)
    logger.debug("  clean_content: %d chars", len(content))

    content = norm_clean_html.clean_html_and_special_chars(content)
    logger.debug("  clean_html: %d chars", len(content))

    try:
        content = norm_tables.process_tables(content)
        logger.debug("  tables: %d chars", len(content))
    except Exception as e:
        logger.warning("  tables FAILED for %s: %s (skipping table normalization)", filename, e)

    tags = norm_metadata.detect_metadata_tags(content)
    year = norm_metadata.detect_year(content)
    doc_hash = norm_dedup.content_hash(content)
    logger.debug("  metadata: tags=%s year=%s hash=%s", tags[:5], year, doc_hash[:8])

    if not skip_synonyms:
        content = norm_synonyms.expand_synonyms(content)

    school = norm_meta.extract_school(filename)
    logger.debug("  school=%s, final %d chars", school, len(content))

    return NormalizedDoc(
        content=content,
        source_url=source_url,
        source_title=source_title,
        filename=filename,
        school=school,
        tags=tags,
        year=year,
        content_hash=doc_hash,
    )


from .norm_meta import *
from .norm_clean_content import *
from .norm_clean_html import *
from .norm_tables import *
from .norm_metadata import *
from .norm_dedup import *
from .norm_synonyms import *

__all__ = ["normalize_document", "NormalizedDoc"]
