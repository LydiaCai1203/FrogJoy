"""
EPUB Index Parser

责任: EPUB 文件 → 逻辑章节 + 段落 (带稳定 ID)

设计文档:
  - docs/paragraph-id-design.md §7 边界情况
  - docs/paragraph-id-prototype-report.md (5 个设计盲点的修复)

不做的事:
  - 翻译 (Phase 2, 需 LLM)
  - 术语识别 (Phase 1/2, 需 LLM)
  - 数据库写入 (IndexService 的职责)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import unquote
from typing import Iterable

import ebooklib
from bs4 import BeautifulSoup, Tag
from ebooklib import epub
from loguru import logger

from .paragraph_id import (
    BookMeta,
    paragraph_id,
    normalize_paragraph,
    normalize_isbn,
)


# 被识别为"段落"的 HTML 块级标签
BLOCK_TAGS = ("p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "li")


# ---------- Data classes ----------

@dataclass
class ParsedParagraph:
    """解析出的段落 (已带稳定 ID)。"""
    pid: str
    chapter_idx: int
    para_idx_in_chapter: int
    text: str


@dataclass
class ParsedChapter:
    """解析出的逻辑章节。"""
    idx: int
    title: str | None
    chapter_fp: str
    paragraphs: list[ParsedParagraph] = field(default_factory=list)


@dataclass
class ParsedBook:
    """完整解析结果。"""
    meta: BookMeta
    book_fingerprint: str           # 由 paragraph_id.book_id 产出
    chapters: list[ParsedChapter] = field(default_factory=list)

    @property
    def total_paragraphs(self) -> int:
        return sum(len(c.paragraphs) for c in self.chapters)


# ---------- Parser ----------

class EpubIndexParser:
    """
    使用示例:
        parser = EpubIndexParser(epub_path)
        parsed = parser.parse()
        for ch in parsed.chapters:
            for p in ch.paragraphs:
                print(p.pid, p.text)
    """

    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self._book: epub.EpubBook | None = None

    # ----- Public API -----

    def parse(self) -> ParsedBook:
        self._book = epub.read_epub(self.epub_path)

        meta = self._extract_meta()
        items = self._spine_items()
        toc_entries = self._flatten_toc(self._book.toc)

        if toc_entries:
            logical_chapters = self._split_by_ncx(items, toc_entries)
        else:
            # Fallback: 以物理文件作章节
            logger.warning(f"EPUB has no TOC, falling back to per-file chapters: {self.epub_path}")
            logical_chapters = self._split_by_physical_file(items)

        from .paragraph_id import book_id as gen_book_id, chapter_fp as gen_cfp
        book_fp = gen_book_id(meta)

        result = ParsedBook(meta=meta, book_fingerprint=book_fp)

        for cidx, (title, paras) in enumerate(logical_chapters):
            chapter = ParsedChapter(
                idx=cidx,
                title=title,
                chapter_fp=gen_cfp(title, cidx),
            )
            prev_text = ""
            for pidx, text in enumerate(paras):
                pid = paragraph_id(meta, title, cidx, pidx, text, prev_text)
                chapter.paragraphs.append(
                    ParsedParagraph(
                        pid=pid,
                        chapter_idx=cidx,
                        para_idx_in_chapter=pidx,
                        text=text,
                    )
                )
                prev_text = text
            result.chapters.append(chapter)

        return result

    # ----- Internals: metadata -----

    def _extract_meta(self) -> BookMeta:
        assert self._book is not None

        def first_or_empty(key: str) -> str:
            items = self._book.get_metadata("DC", key)
            return items[0][0] if items else ""

        title = first_or_empty("title")
        author = first_or_empty("creator")

        isbn = None
        for ident_text, _ in self._book.get_metadata("DC", "identifier"):
            parsed = normalize_isbn(str(ident_text))
            if parsed:
                isbn = parsed
                break

        return BookMeta(title=title, author=author, isbn=isbn)

    # ----- Internals: spine -----

    def _spine_items(self) -> list[epub.EpubHtml]:
        assert self._book is not None
        items: list[epub.EpubHtml] = []
        for itemref in self._book.spine:
            item_id = itemref[0] if isinstance(itemref, tuple) else itemref
            item = self._book.get_item_with_id(item_id)
            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                items.append(item)
        return items

    # ----- Internals: TOC -----

    def _flatten_toc(self, toc) -> list[tuple[str, str]]:
        """
        ebooklib 的 book.toc 是嵌套. 扁平化到 [(title, href), ...]
        处理两种条目:
          - tuple: (Section, children)
          - 直接对象 (Link): 有 .title / .href
        """
        out: list[tuple[str, str]] = []

        def walk(items):
            for entry in items:
                if isinstance(entry, tuple):
                    link, children = entry
                    if hasattr(link, "title") and hasattr(link, "href"):
                        out.append((link.title, link.href))
                    walk(children)
                elif hasattr(entry, "title") and hasattr(entry, "href"):
                    out.append((entry.title, entry.href))

        walk(toc)
        return out

    # ----- Internals: block extraction -----

    def _extract_ordered_blocks(
        self, html: str
    ) -> list[tuple[str, str, list[str]]]:
        """
        按顺序提取 (tag_name, text, anchor_ids)。

        anchor_ids 包括:
          - block 自身和所有后代的 id (NCX anchor 常在子代 <span id="">)
          - 本 block 前面空标签遗留的 pending anchor

        盲点处理 (见 paragraph-id-prototype-report.md §4):
          1. ebooklib get_body_content() 不带 <body>,需 <root> 包裹
          2. anchor 常在 block 子代 span 里
          3. 空 block (仅图片/anchor) 需 anchor 顺延
        """
        # 用 <root> 包裹避免 body=None 问题
        soup = BeautifulSoup(f"<root>{html}</root>", "html.parser")
        root = soup.root if soup.root else soup

        blocks: list[tuple[str, str, list[str]]] = []
        pending_anchors: list[str] = []

        for el in root.descendants:
            if not isinstance(el, Tag):
                continue

            # 记录 block 外独立的空标签 anchor
            if el.name in {"span", "a", "div"} and el.get("id"):
                has_block_ancestor = any(
                    p.name in BLOCK_TAGS for p in el.parents if isinstance(p, Tag)
                )
                if not has_block_ancestor:
                    text = normalize_paragraph(el.get_text(" ", strip=True))
                    if not text:
                        pending_anchors.append(el["id"])

            if el.name in BLOCK_TAGS:
                has_block_ancestor = any(
                    p.name in BLOCK_TAGS for p in el.parents if isinstance(p, Tag)
                )
                if has_block_ancestor:
                    continue

                text = normalize_paragraph(el.get_text(" ", strip=True))

                own_ids: list[str] = []
                if el.get("id"):
                    own_ids.append(el["id"])
                for desc in el.descendants:
                    if isinstance(desc, Tag) and desc.get("id"):
                        own_ids.append(desc["id"])

                all_anchors = pending_anchors + own_ids

                if text:
                    blocks.append((el.name, text, all_anchors))
                    pending_anchors = []
                else:
                    # 空 block: anchor 顺延
                    pending_anchors = all_anchors

        return blocks

    # ----- Internals: chapter splitting -----

    def _split_by_ncx(
        self,
        items: list[epub.EpubHtml],
        toc_entries: list[tuple[str, str]],
    ) -> list[tuple[str, list[str]]]:
        """
        用 NCX 的 href#anchor 把所有 block 切成章节序列。
        """
        # 每文件的 block 序列
        file_blocks: dict[str, list[tuple[str, str, list[str]]]] = {}
        for item in items:
            name = item.get_name()
            html = item.get_body_content()
            if isinstance(html, bytes):
                html = html.decode("utf-8", errors="replace")
            file_blocks[name] = self._extract_ordered_blocks(html)

        # 全局 flat 序列
        flat_blocks: list[tuple[str, int, str, str, list[str]]] = []
        for item in items:
            name = item.get_name()
            for i, (tag, text, anchors) in enumerate(file_blocks.get(name, [])):
                flat_blocks.append((name, i, tag, text, anchors))

        # anchor → flat_idx
        anchor_to_flat_idx: dict[tuple[str, str], int] = {}
        for flat_idx, (name, _, _, _, anchors) in enumerate(flat_blocks):
            for anchor in anchors:
                anchor_to_flat_idx[(name, anchor)] = flat_idx

        # 每个 TOC 条目定位到 flat_idx
        chapter_starts: list[tuple[str, int]] = []
        for title, href in toc_entries:
            if "#" in href:
                path, anchor = href.split("#", 1)
            else:
                path, anchor = href, None
            path = unquote(path)
            anchor = unquote(anchor) if anchor else None

            if anchor and (path, anchor) in anchor_to_flat_idx:
                start = anchor_to_flat_idx[(path, anchor)]
            else:
                start = next(
                    (i for i, b in enumerate(flat_blocks) if b[0] == path),
                    None,
                )
            if start is not None:
                chapter_starts.append((title, start))

        chapter_starts = sorted(set(chapter_starts), key=lambda x: x[1])

        # 切片
        chapters: list[tuple[str, list[str]]] = []
        for i, (title, start) in enumerate(chapter_starts):
            end = (
                chapter_starts[i + 1][1]
                if i + 1 < len(chapter_starts)
                else len(flat_blocks)
            )
            paras = [flat_blocks[j][3] for j in range(start, end)]
            chapters.append((title, paras))

        return chapters

    def _split_by_physical_file(
        self, items: list[epub.EpubHtml]
    ) -> list[tuple[str | None, list[str]]]:
        """Fallback: 无 NCX 时按物理文件切章节。"""
        chapters: list[tuple[str | None, list[str]]] = []
        for item in items:
            html = item.get_body_content()
            if isinstance(html, bytes):
                html = html.decode("utf-8", errors="replace")
            blocks = self._extract_ordered_blocks(html)
            paras = [text for _, text, _ in blocks]
            # 尝试拿首个 h 标签作标题
            title = self._extract_first_heading(item)
            chapters.append((title, paras))
        return chapters

    def _extract_first_heading(self, item: epub.EpubHtml) -> str | None:
        html = item.get_body_content()
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")
        soup = BeautifulSoup(f"<root>{html}</root>", "html.parser")
        for tag in ("h1", "h2", "h3"):
            h = soup.find(tag)
            if h:
                return normalize_paragraph(h.get_text(" ", strip=True))
        return None
