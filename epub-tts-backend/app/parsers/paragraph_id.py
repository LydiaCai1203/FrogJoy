"""
Paragraph ID 稳定算法

设计文档: docs/paragraph-id-design.md
验证报告: docs/paragraph-id-prototype-report.md

核心格式:
    paragraph_id = {book_id}:{chapter_fp}:{content_fp}

  - book_id     ISBN 优先, 退化到 "作者+标题" 签名
  - chapter_fp  章节标题归一化后的 hash (不依赖章节序号)
  - content_fp  段落内容 hash + 章内位置消歧
"""
import re
from dataclasses import dataclass
from hashlib import blake2b


@dataclass
class BookMeta:
    """用于生成 book_id 的书籍元信息。"""
    title: str
    author: str
    isbn: str | None = None


# ---------- ISBN 校验 ----------

def _is_valid_isbn13(digits: str) -> bool:
    """EAN-13 校验位验证"""
    if len(digits) != 13 or not digits.isdigit():
        return False
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


def normalize_isbn(raw: str) -> str | None:
    """
    从原始字符串提取有效 ISBN (10 或 13 位)。

    例如 EPUB 的 <dc:identifier> 里常塞 UUID/ASIN,
    这里只接受通过校验位验证的 ISBN。
    """
    if not raw:
        return None
    clean = re.sub(r"[^\dX]", "", raw.upper())
    if _is_valid_isbn13(clean):
        return clean
    if _is_valid_isbn10(clean):
        return clean
    return None


# ---------- book_id ----------

def book_id(meta: BookMeta) -> str:
    """
    生成书的稳定 ID。
    优先 ISBN (经校验),退化到 "作者+标题" 签名。
    """
    isbn = normalize_isbn(meta.isbn) if meta.isbn else None
    if isbn:
        return f"isbn:{isbn}"
    sig = f"{meta.author.strip().lower()}|{meta.title.strip().lower()}"
    return f"sig:{blake2b(sig.encode(), digest_size=8).hexdigest()}"


# ---------- chapter_fp ----------

_CHAPTER_PREFIX_RE = re.compile(
    r"^\s*("
    r"chapter\s+\d+"                                    # Chapter 3
    r"|第\s*[一二三四五六七八九十百\d]+\s*章"              # 第三章 / 第3章
    r"|\d+[\.\)]"                                       # 3. / 3)
    r")\s*[:：]?\s*",
    flags=re.IGNORECASE,
)


def chapter_fp(chapter_title: str | None, chapter_idx: int) -> str:
    """
    章节指纹。

    策略: 标题归一化 (剥离序号前缀, 空白压缩, 小写) 后 hash。
    无标题章节退化到 idx{chapter_idx}。
    """
    if not chapter_title:
        return f"idx{chapter_idx:03d}"

    t = _CHAPTER_PREFIX_RE.sub("", chapter_title).strip().lower()
    t = re.sub(r"\s+", "_", t)

    if not t:
        return f"idx{chapter_idx:03d}"

    return blake2b(t.encode(), digest_size=4).hexdigest()


# ---------- content_fp ----------

def normalize_paragraph(text: str) -> str:
    """
    段落文本归一化: 只压缩空白,保留大小写 (保护专有名词)。
    """
    return re.sub(r"\s+", " ", text).strip()


def content_fp(text: str, para_idx_in_chapter: int, prev_text: str = "") -> str:
    """
    段落内容指纹 + 章内位置消歧。
    短文本 (<20 字符) 用 prev_text 前 30 字符补强, 避免 "Yes." 类碰撞。
    """
    norm = normalize_paragraph(text)
    if len(norm) < 20 and prev_text:
        key = f"{norm}|prev:{prev_text[:30]}"
    else:
        key = norm
    content_hash = blake2b(key.encode(), digest_size=6).hexdigest()
    return f"{content_hash}-{para_idx_in_chapter:03x}"


# ---------- 顶层 API ----------

def paragraph_id(
    meta: BookMeta,
    chapter_title: str | None,
    chapter_idx: int,
    para_idx_in_chapter: int,
    text: str,
    prev_text: str = "",
) -> str:
    """
    生成段落稳定 ID。

    格式: book_id:chapter_fp:content_fp
    """
    return (
        f"{book_id(meta)}:"
        f"{chapter_fp(chapter_title, chapter_idx)}:"
        f"{content_fp(text, para_idx_in_chapter, prev_text)}"
    )
