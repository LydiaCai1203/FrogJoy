"""
EPUB → Index Parser 模块

对应设计文档:
  - docs/book-as-indexed-knowledge-base.md
  - docs/paragraph-id-design.md
  - docs/paragraph-id-prototype-report.md

主要导出:
  - BookMeta, paragraph_id: 段落稳定 ID 生成
  - EpubIndexParser: EPUB → 逻辑章节 + 段落管线
  - ParsedParagraph, ParsedChapter: 数据类
"""

from .paragraph_id import BookMeta, paragraph_id, book_id, chapter_fp
from .epub_parser import (
    EpubIndexParser,
    ParsedParagraph,
    ParsedChapter,
    ParsedBook,
)

__all__ = [
    "BookMeta",
    "paragraph_id",
    "book_id",
    "chapter_fp",
    "EpubIndexParser",
    "ParsedParagraph",
    "ParsedChapter",
    "ParsedBook",
]
