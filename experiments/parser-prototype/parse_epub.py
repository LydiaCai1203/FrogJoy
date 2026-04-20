"""
真实 EPUB 测试 — 《无条件养育》

步骤:
  1. 读 EPUB, 提取元信息
  2. 从 NCX/NAV 读逻辑章节 (title + href#anchor)
  3. 用 anchor 切 HTML, 两 anchor 之间 = 一个逻辑章节
  4. 每章切段落
  5. 生成 paragraph_id
  6. 统计 + 报告
"""
import sys
from collections import Counter
from urllib.parse import unquote

import ebooklib
from bs4 import BeautifulSoup, Tag
from ebooklib import epub

from paragraph_id import (
    BookMeta,
    paragraph_id,
    normalize_paragraph,
    _normalize_isbn,
    book_id as gen_book_id,
    chapter_fp as gen_cfp,
)


import sys as _sys
EPUB_PATH = _sys.argv[1] if len(_sys.argv) > 1 else "/Users/caiqj/Downloads/无条件养育/无条件养育.epub"

BLOCK_TAGS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "li"]


def get_metadata(book: epub.EpubBook) -> BookMeta:
    def first_or_empty(key: str) -> str:
        items = book.get_metadata("DC", key)
        return items[0][0] if items else ""

    title = first_or_empty("title")
    author = first_or_empty("creator")

    isbn = None
    for ident_text, _ in book.get_metadata("DC", "identifier"):
        parsed = _normalize_isbn(str(ident_text))
        if parsed:
            isbn = parsed
            break

    return BookMeta(title=title, author=author, isbn=isbn)


def flatten_toc(toc, out: list | None = None) -> list[tuple[str, str]]:
    """
    ebooklib 的 book.toc 是嵌套结构. 扁平化到 [(title, href), ...]
    href 形如 "text00000.html#filepos0000047756"
    """
    if out is None:
        out = []
    for entry in toc:
        if isinstance(entry, tuple):
            # (Section, children)
            link, children = entry
            if hasattr(link, "title") and hasattr(link, "href"):
                out.append((link.title, link.href))
            flatten_toc(children, out)
        else:
            if hasattr(entry, "title") and hasattr(entry, "href"):
                out.append((entry.title, entry.href))
    return out


def extract_ordered_blocks(html: str) -> list[tuple[str, str, list[str]]]:
    """
    按顺序提取 (tag_name, text, anchor_ids).
    anchor_ids: 该 block 自身或其任意子代里的所有 id,
                + block 之前但还没有被 block 消费的空标签 id.

    注意: ebooklib 的 get_body_content() 返回无 <body> 包裹的 HTML 片段,
    需要遍历 soup 的顶层元素和其后代.
    """
    # 包一层方便 BeautifulSoup 处理
    soup = BeautifulSoup(f"<root>{html}</root>", "html.parser")
    root = soup.root if soup.root else soup

    blocks: list[tuple[str, str, list[str]]] = []
    pending_anchors: list[str] = []

    for el in root.descendants:
        if not isinstance(el, Tag):
            continue

        # 独立的 anchor 标签 (没 block 祖先)
        if el.name in {"span", "a", "div"} and el.get("id"):
            has_block_ancestor = any(
                p.name in BLOCK_TAGS for p in el.parents if isinstance(p, Tag)
            )
            if not has_block_ancestor:
                # block 外独立的 anchor
                text = normalize_paragraph(el.get_text(" ", strip=True))
                if not text:
                    pending_anchors.append(el["id"])
                # 有文字的 span 就忽略, 让外层 block 处理

        if el.name in BLOCK_TAGS:
            has_block_ancestor = any(
                p.name in BLOCK_TAGS for p in el.parents if isinstance(p, Tag)
            )
            if has_block_ancestor:
                continue

            text = normalize_paragraph(el.get_text(" ", strip=True))

            # 本 block 自身 + 所有后代的 id
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
                # 空 block (只有图片/anchor), anchor 顺延
                pending_anchors = all_anchors

    return blocks


def split_by_ncx(
    items: list[epub.EpubHtml],
    toc_entries: list[tuple[str, str]],
) -> list[tuple[str, list[str]]]:
    """
    用 TOC 里的 href#anchor 切分 HTML.
    策略:
      1. 为每个 spine 文件提取 ordered blocks (带 anchor)
      2. 构造一个全局的 (file, anchor) → block_idx 映射
      3. 根据 TOC 顺序, 划出每个章节的 block 区间
    """
    # 每个 item 的 ordered blocks
    file_blocks: dict[str, list[tuple[str, str, str | None]]] = {}
    for item in items:
        name = item.get_name()
        html = item.get_body_content()
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")
        file_blocks[name] = extract_ordered_blocks(html)

    # 所有 block 展平 (保持 spine 顺序)
    flat_blocks = []  # (file, block_idx_in_file, tag, text, anchors)
    for item in items:
        name = item.get_name()
        for i, (tag, text, anchors) in enumerate(file_blocks.get(name, [])):
            flat_blocks.append((name, i, tag, text, anchors))

    # anchor 到 flat_idx 的映射 (一个 block 可能有多个 anchor)
    anchor_to_flat_idx: dict[tuple[str, str], int] = {}
    for flat_idx, (name, _, _, _, anchors) in enumerate(flat_blocks):
        for anchor in anchors:
            anchor_to_flat_idx[(name, anchor)] = flat_idx

    # 每个 TOC 条目定位到 flat_idx
    chapter_starts = []  # (title, flat_idx)
    for title, href in toc_entries:
        # href 形如 "text00000.html#filepos0000047756" 或 "text00000.html"
        if "#" in href:
            path, anchor = href.split("#", 1)
        else:
            path, anchor = href, None
        path = unquote(path)
        anchor = unquote(anchor) if anchor else None

        # 找到 start flat_idx
        if anchor and (path, anchor) in anchor_to_flat_idx:
            start = anchor_to_flat_idx[(path, anchor)]
        else:
            # 无 anchor / 找不到 anchor: 定位到该文件的第一个 block
            start = next(
                (i for i, b in enumerate(flat_blocks) if b[0] == path),
                None,
            )
        if start is not None:
            chapter_starts.append((title, start))

    # 去重 + 排序
    chapter_starts = sorted(set(chapter_starts), key=lambda x: x[1])

    # 切片
    chapters: list[tuple[str, list[str]]] = []
    for i, (title, start) in enumerate(chapter_starts):
        end = chapter_starts[i + 1][1] if i + 1 < len(chapter_starts) else len(flat_blocks)
        paras = [flat_blocks[j][3] for j in range(start, end)]
        chapters.append((title, paras))

    return chapters


def main():
    print(f"\n正在解析: {EPUB_PATH}\n")
    book = epub.read_epub(EPUB_PATH)

    meta = get_metadata(book)
    print(f"书名:    {meta.title}")
    print(f"作者:    {meta.author}")
    print(f"ISBN:    {meta.isbn or '(无 或 无效)'}")
    bid = gen_book_id(meta)
    print(f"book_id: {bid}")
    print()

    # spine
    items = []
    for itemref in book.spine:
        item_id = itemref[0] if isinstance(itemref, tuple) else itemref
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
            items.append(item)

    print(f"EPUB 物理文件数 (spine): {len(items)}")

    # NCX / NAV
    toc_entries = flatten_toc(book.toc)
    print(f"TOC 条目数: {len(toc_entries)}")
    print()

    if not toc_entries:
        print("⚠️ 没有 TOC 信息, 退化到物理文件切分")
        return 1

    # 用 NCX 切章节
    chapters = split_by_ncx(items, toc_entries)
    print(f"逻辑章节数 (按 NCX anchor 切): {len(chapters)}")
    print()

    # 生成 paragraph_id
    all_rows = []
    for cidx, (title, paras) in enumerate(chapters):
        prev_text = ""
        for pidx, text in enumerate(paras):
            pid = paragraph_id(
                meta=meta,
                chapter_title=title,
                chapter_idx=cidx,
                para_idx_in_chapter=pidx,
                text=text,
                prev_text=prev_text,
            )
            all_rows.append((pid, text, title, cidx, pidx))
            prev_text = text

    # 章节概览
    print("=" * 80)
    print("逻辑章节概览")
    print("=" * 80)
    for cidx, (title, paras) in enumerate(chapters):
        title_display = (title or "[无标题]")[:36]
        first_preview = paras[0][:30] if paras else ""
        cfp = gen_cfp(title, cidx)
        print(f"  [{cidx:02d}] fp={cfp:<8} {title_display:<38} | {len(paras):4d}段 | {first_preview}")

    print()
    print("=" * 80)
    print("段落样例 (每章第 2 段, 避免章节标题)")
    print("=" * 80)
    shown = 0
    seen_chapters = set()
    for row in all_rows:
        pid, text, title, cidx, pidx = row
        if cidx in seen_chapters:
            continue
        # 跳过首段 (通常是章节标题)
        if pidx < 1:
            continue
        seen_chapters.add(cidx)
        shown += 1
        if shown > 8:
            break
        text_preview = text[:70] + "..." if len(text) > 70 else text
        chap = (title or f"idx{cidx}")[:30]
        print(f"\n  ch{cidx:02d}:{pidx:03d} [{chap}]")
        print(f"    pid: {pid}")
        print(f"    txt: {text_preview}")

    # 统计
    print()
    print("=" * 80)
    print("关键统计")
    print("=" * 80)
    print(f"逻辑章节数:       {len(chapters)}")
    print(f"总段落数:         {len(all_rows)}")

    id_counts = Counter(pid for pid, _, _, _, _ in all_rows)
    dup_ids = {pid: n for pid, n in id_counts.items() if n > 1}
    print(f"ID 唯一性:        {'✓ 无冲突' if not dup_ids else f'✗ {len(dup_ids)} 个 ID 冲突'}")

    lens = [len(row[1]) for row in all_rows]
    if lens:
        avg_len = sum(lens) / len(lens)
        short = sum(1 for l in lens if l < 20)
        print(f"平均段长:         {avg_len:.0f} 字")
        print(f"短段落 (<20):    {short} 段 ({short * 100 / len(lens):.1f}%)")

    chapter_sizes = [len(paras) for _, paras in chapters]
    if chapter_sizes:
        print(f"章节段落分布:     min={min(chapter_sizes)}, max={max(chapter_sizes)}, "
              f"avg={sum(chapter_sizes) / len(chapter_sizes):.0f}, "
              f"median={sorted(chapter_sizes)[len(chapter_sizes)//2]}")

    # chapter_fp 退化比例
    fallback = sum(1 for title, _ in chapters if gen_cfp(title, 0).startswith("idx"))
    total_chapters = len(chapters)
    print(f"有效 chapter_fp:  {total_chapters - fallback}/{total_chapters} 章 ({(total_chapters - fallback) * 100 / total_chapters:.0f}% 标题命中)")

    # 章节标题有无碰撞 (同书内 chapter_fp 碰撞 = 潜在风险)
    cfp_counts = Counter(gen_cfp(title, idx) for idx, (title, _) in enumerate(chapters))
    cfp_dups = {k: v for k, v in cfp_counts.items() if v > 1}
    if cfp_dups:
        print(f"⚠️ chapter_fp 碰撞: {len(cfp_dups)} 组")
        for fp, cnt in list(cfp_dups.items())[:3]:
            titles = [t for t, _ in chapters if gen_cfp(t, 0) == fp]
            print(f"    {fp}: {titles[:3]}")
    else:
        print(f"chapter_fp 全部唯一: ✓")

    # 确定性验证
    print()
    print("=" * 80)
    print("确定性验证")
    print("=" * 80)
    second_pass = []
    for cidx, (title, paras) in enumerate(chapters):
        prev_text = ""
        for pidx, text in enumerate(paras):
            pid = paragraph_id(meta, title, cidx, pidx, text, prev_text)
            second_pass.append(pid)
            prev_text = text
    all_match = [r[0] for r in all_rows] == second_pass
    print(f"  {'✓' if all_match else '✗'} 两次生成 ID 完全一致")

    # 冲突详情
    if dup_ids:
        print()
        print("=" * 80)
        print("⚠️ ID 冲突详情 (前 5 个)")
        print("=" * 80)
        shown_count = 0
        for pid, count in sorted(dup_ids.items(), key=lambda x: -x[1]):
            if shown_count >= 5:
                break
            print(f"\n  ID: {pid} (出现 {count} 次)")
            for row in all_rows:
                if row[0] == pid:
                    print(f"    → ch{row[3]}:{row[4]} "
                          f"'{(row[2] or '[无标题]')[:20]}' | {row[1][:50]}")
            shown_count += 1

    return 0 if not dup_ids and all_match and not cfp_dups else 1


if __name__ == "__main__":
    sys.exit(main())
