"""
Paragraph ID 稳定算法 —— MVP 实现

对应设计文档: docs/paragraph-id-design.md
"""
import re
from dataclasses import dataclass
from hashlib import blake2b


@dataclass
class BookMeta:
    title: str
    author: str
    isbn: str | None = None


def _is_valid_isbn13(digits: str) -> bool:
    """ISBN-13 校验位验证 (EAN-13 算法)"""
    if len(digits) != 13 or not digits.isdigit():
        return False
    # EAN-13: 前 12 位加权 (奇数位×1, 偶数位×3), 总和 mod 10 的反数 = 校验位
    total = 0
    for i, c in enumerate(digits[:12]):
        total += int(c) * (3 if i % 2 else 1)
    check = (10 - total % 10) % 10
    return check == int(digits[12])


def _is_valid_isbn10(s: str) -> bool:
    """ISBN-10 校验"""
    s = s.upper()
    if len(s) != 10:
        return False
    if not (s[:9].isdigit() and (s[9].isdigit() or s[9] == "X")):
        return False
    total = sum((i + 1) * (10 if s[i] == "X" else int(s[i])) for i in range(9))
    check = total % 11
    last = 10 if s[9] == "X" else int(s[9])
    return check == last


def _normalize_isbn(raw: str) -> str | None:
    """从原始字符串提取有效 ISBN (10 或 13 位)"""
    if not raw:
        return None
    clean = re.sub(r"[^\dX]", "", raw.upper())
    if _is_valid_isbn13(clean):
        return clean
    if _is_valid_isbn10(clean):
        return clean
    return None


def book_id(meta: BookMeta) -> str:
    """
    优先 ISBN (经校验), 退化到作者+标题签名.
    """
    isbn = _normalize_isbn(meta.isbn) if meta.isbn else None
    if isbn:
        return f"isbn:{isbn}"
    sig = f"{meta.author.strip().lower()}|{meta.title.strip().lower()}"
    return f"sig:{blake2b(sig.encode(), digest_size=8).hexdigest()}"


# 章节序号前缀: 英文 "Chapter 3:", 中文 "第三章"/"第3章", 数字 "3."
_CHAPTER_PREFIX_RE = re.compile(
    r"^\s*("
    r"chapter\s+\d+"
    r"|第\s*[一二三四五六七八九十百\d]+\s*章"
    r"|\d+[\.\)]"
    r")\s*[:：]?\s*",
    flags=re.IGNORECASE,
)


def chapter_fp(chapter_title: str | None, chapter_idx: int) -> str:
    """
    章节指纹: 标题归一化后 hash, 不依赖序号.
    """
    if not chapter_title:
        return f"idx{chapter_idx:03d}"

    t = _CHAPTER_PREFIX_RE.sub("", chapter_title).strip().lower()
    t = re.sub(r"\s+", "_", t)

    if not t:
        return f"idx{chapter_idx:03d}"

    return blake2b(t.encode(), digest_size=4).hexdigest()


def normalize_paragraph(text: str) -> str:
    """
    只压缩空白, 保留大小写 (保护专有名词).
    """
    return re.sub(r"\s+", " ", text).strip()


def content_fp(text: str, para_idx_in_chapter: int, prev_text: str = "") -> str:
    """
    内容指纹 + 章内位置消歧.
    短文本用 prev_text 前 30 字符补强.
    """
    norm = normalize_paragraph(text)
    if len(norm) < 20 and prev_text:
        key = f"{norm}|prev:{prev_text[:30]}"
    else:
        key = norm
    content_hash = blake2b(key.encode(), digest_size=6).hexdigest()
    return f"{content_hash}-{para_idx_in_chapter:03x}"


def paragraph_id(
    meta: BookMeta,
    chapter_title: str | None,
    chapter_idx: int,
    para_idx_in_chapter: int,
    text: str,
    prev_text: str = "",
) -> str:
    return (
        f"{book_id(meta)}:"
        f"{chapter_fp(chapter_title, chapter_idx)}:"
        f"{content_fp(text, para_idx_in_chapter, prev_text)}"
    )
