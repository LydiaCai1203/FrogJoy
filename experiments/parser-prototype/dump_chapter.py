"""
Dump 指定章节的段落 + paragraph_id 到 JSON, 供 extractor 原型测试使用.
"""
import json
import sys
from pathlib import Path

import ebooklib
from ebooklib import epub

from parse_epub import (
    get_metadata,
    flatten_toc,
    split_by_ncx,
)
from paragraph_id import paragraph_id


def main():
    epub_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/caiqj/Downloads/无条件养育/无条件养育.epub"
    # 要 dump 的章节 (通过首段文字匹配, 避免依赖 idx)
    target_titles = sys.argv[2:] if len(sys.argv) > 2 else [
        "第一章",     # 匹配 "第一章 有条件养育"
        "两种养育模式的理论基础",
        "有条件养育的后果",
    ]

    book = epub.read_epub(epub_path)
    meta = get_metadata(book)
    toc_entries = flatten_toc(book.toc)

    items = []
    for itemref in book.spine:
        item_id = itemref[0] if isinstance(itemref, tuple) else itemref
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
            items.append(item)

    chapters = split_by_ncx(items, toc_entries)

    # 选出目标章节
    selected = []
    for cidx, (title, paras) in enumerate(chapters):
        if any(t in (title or "") for t in target_titles):
            selected.append((cidx, title, paras))

    if not selected:
        print(f"未找到章节: {target_titles}", file=sys.stderr)
        sys.exit(1)

    # 构造 dump
    output = {
        "book": {
            "title": meta.title,
            "author": meta.author,
            "isbn": meta.isbn,
        },
        "chapters": [],
    }

    for cidx, title, paras in selected:
        chapter_data = {
            "chapter_idx": cidx,
            "title": title,
            "paragraphs": [],
        }
        prev_text = ""
        for pidx, text in enumerate(paras):
            pid = paragraph_id(meta, title, cidx, pidx, text, prev_text)
            chapter_data["paragraphs"].append({
                "pid": pid,
                "idx": pidx,
                "text": text,
            })
            prev_text = text
        output["chapters"].append(chapter_data)

    out_path = Path(__file__).parent / "chapter_dump.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    total_paras = sum(len(c["paragraphs"]) for c in output["chapters"])
    total_chars = sum(len(p["text"]) for c in output["chapters"] for p in c["paragraphs"])

    print(f"✓ 已 dump 到 {out_path}")
    print(f"  书名:   {meta.title}")
    print(f"  章节数: {len(selected)}")
    print(f"  段落数: {total_paras}")
    print(f"  字符数: {total_chars}")
    for cidx, title, paras in selected:
        print(f"  [{cidx:02d}] {title}  ({len(paras)}段)")


if __name__ == "__main__":
    main()
