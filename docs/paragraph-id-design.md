# Paragraph ID 稳定算法设计

> 本文档是宪法 `book-as-indexed-knowledge-base.md` 的技术附录。
>
> Paragraph ID 是 Index Layer 的**地基的地基**。搞错了，未来所有跳转、批注、划线、复习都会破。

---

## 0. TL;DR

- **格式**：`{book_id}:{chapter_fp}:{content_fp}`
- **book_id**：ISBN 优先，退化到 `作者+标题` 签名
- **chapter_fp**：章节标题归一化后 hash（不依赖序号）
- **content_fp**：段落内容 hash + 章内位置消歧
- **跨版本批注**：fuzzy migration — 同章同位置附近的高相似度段落自动迁移
- **MVP 实现 ~50 行 Python 足够**

---

## 1. 要解决什么问题

给 EPUB 里每个段落生成一个 ID，让它成为所有索引、批注、跳转、划线的锚点。

### 1.1 硬约束（必须满足）

1. **确定性**：同输入永远产生同 ID（reproducible）
2. **唯一性**：同一本书内不冲突
3. **稳定性**：重新解析同一 EPUB 不换 ID（annotations 不丢）

### 1.2 软目标（尽量满足）

4. **鲁棒性**：作者改一个错字，ID 不彻底崩盘
5. **跨版本识别**：不同出版版本的同一段能被关联

### 1.3 什么不是这个算法的责任

- ❌ 不负责"这段话说了什么"（那是 Index Layer 的 concepts/occurrences）
- ❌ 不负责排版/样式（那是 Renderer 的事）
- ❌ 不负责段落内的字符级定位（那是划线锚点的下一层）

---

## 2. 朴素方案及其失败模式

### 方案 A：纯内容哈希

```python
pid = sha256(text)[:16]
```

失败模式：
- ❌ 空段落、版权页、章节分隔符等重复文本碰撞
- ❌ 两个章节出现相同标题 / 相同短语碰撞
- ❌ 作者改一个字，ID 完全变（连带所有批注飘掉）

### 方案 B：纯位置

```python
pid = f"{chapter_idx}:{paragraph_idx}"
```

失败模式：
- ❌ 出版社重排章节 → 全部 ID 偏移
- ❌ 插入/删除段落 → 后续全部错位
- ❌ 用户批注整体飘

### 方案 C：简单拼接

```python
pid = sha256(f"{chapter_idx}:{paragraph_idx}:{text}")[:16]
```

失败模式：
- ❌ 编辑任何一位都改 ID
- ❌ 不同版本完全无法匹配

---

## 3. 设计原则

基于失败模式反推：

1. **内容归一化后再哈希** — 空白/全半角差异不应影响 ID
2. **内容哈希为主，位置为辅** — 相同段落重复出现时靠位置消歧
3. **ID 分段分层** — `book:chapter:paragraph` 三段，每段独立稳定
4. **保留 fallback 信息** — 即使 ID 变，能靠"第一句/长度/前后上下文"恢复

---

## 4. 推荐方案：三段式稳定 ID

### 4.1 格式

```
paragraph_id = {book_id}:{chapter_fp}:{content_fp}
```

- `book_id`：书的稳定 ID
- `chapter_fp`：章节指纹（chapter fingerprint）
- `content_fp`：段落内容指纹 + 章内位置

### 4.2 `book_id` 生成

```python
def book_id(metadata: BookMeta) -> str:
    if metadata.isbn:
        clean_isbn = re.sub(r'[^\dX]', '', metadata.isbn.upper())
        return f"isbn:{clean_isbn}"
    sig = f"{metadata.author.strip().lower()}|{metadata.title.strip().lower()}"
    return f"sig:{blake2b(sig.encode(), digest_size=8).hexdigest()}"
```

**理由**：
- ISBN 是出版行业天然主键，最稳
- 没 ISBN 退化到 `作者+标题` 签名
- 同书不同版本（假设作者+标题相同） → 同 `book_id`

**反例**：译本和原著共享 ISBN 是极少数，因此中译本 ≠ 英文原版，符合预期。

### 4.3 `chapter_fp` 生成

```python
def chapter_fp(chapter_title: str | None, chapter_idx: int) -> str:
    if not chapter_title:
        return f"idx{chapter_idx:03d}"

    # 去章节序号前缀
    # "Chapter 3: The ATR Trap" → "the atr trap"
    # "第三章 启发式" → "启发式"
    # "3. Introduction" → "introduction"
    t = re.sub(
        r'^\s*(chapter\s+\d+|第\s*[一二三四五六七八九十百\d]+\s*章|\d+[\.\)])\s*[:：]?\s*',
        '', chapter_title, flags=re.IGNORECASE
    ).strip().lower()
    t = re.sub(r'\s+', '_', t)

    if not t:
        return f"idx{chapter_idx:03d}"

    return blake2b(t.encode(), digest_size=4).hexdigest()
```

**理由**：
- 同一本书的不同版本章节可能重排 → 不能用 index
- 标题是最稳定的章节身份
- 无标题章节（前言、附录）退化到 index

**代价**：重命名章节会改 `chapter_fp` → 需要 fuzzy migration 修复（见 §6）。

### 4.4 `content_fp` 生成（核心）

```python
def normalize_paragraph(text: str) -> str:
    # 多空白 → 单空格, trim
    t = re.sub(r'\s+', ' ', text).strip()
    # 不做大小写归一 — 英文专有名词敏感 (MIT ≠ mit)
    # 可选: NFKC 全半角归一
    return t


def content_fp(text: str, para_idx_in_chapter: int, prev_text: str = "") -> str:
    norm = normalize_paragraph(text)

    # 短文本容易碰撞, 靠前一段补强
    if len(norm) < 20 and prev_text:
        key = f"{norm}|prev:{prev_text[:30]}"
    else:
        key = norm

    content_hash = blake2b(key.encode(), digest_size=6).hexdigest()
    pos_tag = f"{para_idx_in_chapter:03x}"   # 支持 0-4095 段

    return f"{content_hash}-{pos_tag}"
```

**关键设计**：
- **归一化只动空白**，保留大小写和标点。保护专有名词。
- **位置是后缀而非哈希成分**。这意味着：
  - 编辑文本 → ID 变（代价，靠 migration 补）
  - 相同段落不同位置 → 仍可区分（通过 pos_tag）
- **pos_tag 是章内索引**，不是全书。章内插入段落才会影响，范围可控。

### 4.5 完整例子

```
Elder《走进我的交易室》Chapter 6, 第 42 段, 文本 "The ATR measures..."

book_id     = "isbn:9780471225348"
chapter_fp  = "a3f1"                    (hash("the_indicators"))
content_fp  = "8e2d1c4a9b03-02a"        (内容 hash + 位置 042)

paragraph_id = "isbn:9780471225348:a3f1:8e2d1c4a9b03-02a"
```

长度约 50 字符，人类可读性一般但完全可接受。

---

## 5. 最小可运行实现

```python
# parser/paragraph_id.py
import re
from dataclasses import dataclass
from hashlib import blake2b


@dataclass
class BookMeta:
    title: str
    author: str
    isbn: str | None = None


def book_id(meta: BookMeta) -> str:
    if meta.isbn:
        clean_isbn = re.sub(r'[^\dX]', '', meta.isbn.upper())
        return f"isbn:{clean_isbn}"
    sig = f"{meta.author.strip().lower()}|{meta.title.strip().lower()}"
    return f"sig:{blake2b(sig.encode(), digest_size=8).hexdigest()}"


def chapter_fp(chapter_title: str | None, chapter_idx: int) -> str:
    if not chapter_title:
        return f"idx{chapter_idx:03d}"
    t = re.sub(
        r'^\s*(chapter\s+\d+|第\s*[一二三四五六七八九十百\d]+\s*章|\d+[\.\)])\s*[:：]?\s*',
        '', chapter_title, flags=re.IGNORECASE
    ).strip().lower()
    t = re.sub(r'\s+', '_', t)
    if not t:
        return f"idx{chapter_idx:03d}"
    return blake2b(t.encode(), digest_size=4).hexdigest()


def normalize_paragraph(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def content_fp(text: str, para_idx_in_chapter: int, prev_text: str = "") -> str:
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
```

**代码量**：约 50 行。MVP v0 够用。

---

## 6. fuzzy migration：编辑后挽救批注

前面的方案缺点：**作者改一个字，ID 变，之前的批注"孤儿"了**。

解决思路：**Index 重建时做一次匹配迁移**。

### 6.1 算法

```python
def migrate_annotations(
    old_paragraphs: list[Paragraph],
    new_paragraphs: list[Paragraph],
    annotations: list[Annotation],
) -> dict[str, str | None]:
    """
    返回 {old_id: new_id or None}
    None 表示孤儿批注, UI 应提示用户
    """
    new_by_id = {p.id: p for p in new_paragraphs}
    mapping: dict[str, str | None] = {}

    for old in old_paragraphs:
        # 1. 完全匹配 (最常见, 多数批注落这)
        if old.id in new_by_id:
            mapping[old.id] = old.id
            continue

        # 2. 同章同位置附近找候选
        old_chapter_fp = old.id.split(':')[1]
        old_pos = int(old.id.split('-')[-1], 16)

        candidates = [
            p for p in new_paragraphs
            if p.id.split(':')[1] == old_chapter_fp
            and abs(
                int(p.id.split('-')[-1], 16) - old_pos
            ) <= 3  # 位置小幅漂移容忍
        ]

        # 3. 相似度打分
        best, best_score = None, 0.0
        for c in candidates:
            s = similarity(old.text, c.text)
            if s > best_score:
                best, best_score = c, s

        # 4. 阈值判定
        if best and best_score > 0.85:
            mapping[old.id] = best.id
        else:
            mapping[old.id] = None

    return mapping


def similarity(a: str, b: str) -> float:
    """MVP: SequenceMatcher 足够. v2 换 embedding 相似度"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()
```

### 6.2 UX

重新解析 EPUB 后，告诉用户：

```
✓ 成功迁移 238 条批注
⚠️ 3 条批注找不到对应段落 [查看孤儿批注]
   (这些段落可能已被作者改动或删除)
```

孤儿批注页里列出原文片段 + 用户的注释，用户可以：
- 手动指定对应的新段落
- 确认删除
- 暂存（不处理）

### 6.3 迁移边界

匹配阈值 0.85 是经验值，需要实际调：
- 太高 → 改错字就变孤儿（烦）
- 太低 → 错误迁移到错误段落（更糟）

MVP 阶段用 SequenceMatcher，v2 换 embedding 相似度会显著更准。

---

## 7. 边界情况

### 7.1 代码块、诗、表格

归一化时需要**保留结构**，不能简单 `\s+` 压缩。

```python
def normalize_paragraph(text: str, preserve_whitespace: bool = False) -> str:
    if preserve_whitespace:
        return text.strip()   # 只 trim, 不压缩内部
    return re.sub(r'\s+', ' ', text).strip()
```

Parser 识别到 `<pre>` / `<code>` / `<table>` 时传 `preserve_whitespace=True`。

### 7.2 非常短的段落

`"Yes."` / `"No."` / `"See Figure 3.1."`

短文本 hash 碰撞风险高。前面 §4.4 已经给了方案：`prev_text` 前 30 字符纳入 hash。

### 7.3 图片 / 图表段落

```python
if paragraph.is_image:
    # 用 src 或 alt 文本作内容
    key = paragraph.img_src or paragraph.alt_text or f"img_{chapter_idx}_{pos}"
    content_hash = blake2b(key.encode(), digest_size=6).hexdigest()
```

### 7.4 EPUB 物理分片 ≠ 逻辑章节

有些出版社把一章拆成多个 `xhtml` 文件，或把多章合到一个文件。

**处理**：Parser 层先按**目录（NCX/NAV）**重组为逻辑章节，不按物理文件。

```python
# 从 EPUB nav 获取逻辑章节顺序
logical_chapters = parse_nav(epub)
# 按逻辑顺序拼接 xhtml, 再切段落
```

### 7.5 前言、附录、致谢

这些通常没有编号章节。退化到 `idx{chapter_idx:03d}` 是安全的，因为它们在书里的相对位置基本稳定。

### 7.6 跨语言书

同书的英文版和中文译本 **不应该** 共享 `book_id`（语言不同，段落完全不同）。

但**应该**有一个"跨版本关联"层指向彼此：

```sql
book_versions:
  canonical_book_id    "卡尼曼_思考快与慢"    (抽象实体, 非 book_id)
  book_id              具体版本的 book_id
  language             "en" / "zh-CN"
  translator           "胡晓姣"
```

这是 v3 的事，v0 不用管。

---

## 8. 测试矩阵

MVP 阶段必跑：

```python
def test_determinism():
    """同输入 → 同 ID"""
    pid1 = paragraph_id(meta, "Ch 1", 0, 5, "Hello world")
    pid2 = paragraph_id(meta, "Ch 1", 0, 5, "Hello world")
    assert pid1 == pid2


def test_whitespace_invariance():
    """空白差异不影响 ID"""
    pid1 = paragraph_id(meta, "Ch 1", 0, 5, "Hello  world")
    pid2 = paragraph_id(meta, "Ch 1", 0, 5, "Hello world")
    assert pid1 == pid2


def test_case_sensitivity_preserved():
    """大小写敏感 (保护专有名词)"""
    pid1 = paragraph_id(meta, "Ch 1", 0, 5, "MIT is a school")
    pid2 = paragraph_id(meta, "Ch 1", 0, 5, "mit is a school")
    assert pid1 != pid2


def test_duplicate_paragraphs_get_different_ids():
    """相同内容不同位置 → 不同 ID"""
    pid1 = paragraph_id(meta, "Ch 1", 0, 5, "...")
    pid2 = paragraph_id(meta, "Ch 1", 0, 9, "...")
    assert pid1 != pid2


def test_chapter_title_disambiguates():
    """不同章节的相同段落 → 不同 ID"""
    pid1 = paragraph_id(meta, "Ch 1", 0, 5, "Hello")
    pid2 = paragraph_id(meta, "Ch 2", 1, 5, "Hello")
    assert pid1 != pid2


def test_same_book_different_chapter_order():
    """章节顺序变 (重排), 章节标题不变 → chapter_fp 不变"""
    # 版本 A: 章节顺序 [intro, body, conclusion]
    # 版本 B: 章节顺序 [intro, conclusion, body]  (重排)
    assert chapter_fp("body", 1) == chapter_fp("body", 2)


def test_book_same_across_editions_by_isbn():
    """同 ISBN → book_id 相同"""
    meta_v1 = BookMeta("X", "Y", "9780000000001")
    meta_v2 = BookMeta("X", "Y", "9780000000001")
    assert book_id(meta_v1) == book_id(meta_v2)


def test_book_no_isbn_falls_back():
    """无 ISBN 用签名"""
    m1 = BookMeta("X", "Y")
    m2 = BookMeta("X", "Y")
    assert book_id(m1) == book_id(m2)
    assert book_id(m1).startswith("sig:")


def test_short_paragraph_uses_prev_context():
    """短段落靠前一段消歧"""
    pid1 = paragraph_id(meta, "Ch 1", 0, 5, "No.", prev_text="Did you?")
    pid2 = paragraph_id(meta, "Ch 1", 0, 5, "No.", prev_text="Are you sure?")
    assert pid1 != pid2


def test_chapter_prefix_stripped():
    """章节序号前缀被剥离, 同标题 hash 相同"""
    assert chapter_fp("Chapter 3: Introduction", 2) == chapter_fp("3. Introduction", 2)
    assert chapter_fp("第三章 启发式", 2) == chapter_fp("3. 启发式", 2)


def test_migration_exact_match():
    """完全相同的段落批注直接保留"""
    # ...

def test_migration_fuzzy():
    """编辑一个字, fuzzy 迁移"""
    # ...
```

---

## 9. 为什么不用其他方案

### 9.1 为什么不用 EPUB CFI

**ePub CFI** 是官方标准，标识 EPUB 内位置的 XPath 样路径：

```
epubcfi(/6/4[chap01ref]!/4[body01]/10[para05]/2/1:3)
```

不用作主 ID 的原因：
- ❌ **路径型**：章节重编排 → 路径全变
- ❌ **不是内容相关**：无法跨版本识别
- ❌ **可读性差**
- ❌ **生态支持有限**

**但 CFI 有用**：作为 `paragraphs` 表的附加字段，用于与其他 EPUB 阅读器跳转兼容。

```sql
paragraphs:
  id         TEXT PRIMARY KEY   -- 我们的稳定 ID (主键)
  epub_cfi   TEXT               -- CFI 字符串 (辅助, 兼容用)
```

### 9.2 为什么不用 UUID

UUID 不是确定性的，每次生成都不同。**违反硬约束 1（确定性）**，根本不满足需求。

### 9.3 为什么不用全书顺序号

- 插入/删除段落整体飘
- 不同版本完全无法对齐
- 等同于方案 B（纯位置）的失败模式

### 9.4 为什么不直接用段落首句

- 首句可能重复（"Chapter 3" 这种）
- 首句可能很长（不适合做 ID）
- 容易被编辑改动
- 失去确定性保障

---

## 10. 长期演进

```
v0 (MVP, 当前)
  ├── 50 行 Python
  ├── SequenceMatcher 相似度
  └── 覆盖 90% 场景

v1 (批注成熟后)
  └── fuzzy migration 正式 UI (孤儿批注管理页)

v2 (需要跨版本对齐)
  ├── Embedding-based 相似度
  │   └── 段落 embedding 预计算存 paragraphs 表
  └── 阈值动态化 (基于书的"变化密度")

v3 (跨语言/跨版本)
  ├── book_versions 表
  ├── 同书多语言版本互指
  └── 段落级跨语言对齐 (Sentence-level aligned)
```

---

## 11. 未决问题

```
Q1: 章节标题同名怎么办?
   场景: Roam 这种书, 两个章节都叫 "Summary"
   现状: chapter_fp 会碰撞
   方案: 碰撞检测时加上 "章内首段前 20 字符" 到 chapter_fp
        或章节级的 pos_tag
   优先级: 低 (实际很少见), 观察后再补

Q2: 章节被拆分/合并怎么办?
   场景: 新版把原 Ch3 拆成 Ch3 + Ch4
   现状: migration 跨章会失败
   方案: migration 时先做全书的 chapter 相似度匹配, 建立章节级映射
   优先级: 中

Q3: 作者匿名、无 ISBN 的书怎么确保 book_id 稳定?
   场景: Samizdat / 网络小说
   现状: 退化到 sig:(author+title)
   方案: 允许用户手动指定 book_id
   优先级: 低

Q4: 多作者协作的书?
   场景: 论文集, 作者字段有多个
   现状: book_id 可能不稳定
   方案: 归一化 author 字段 (按字母排序后拼接)
   优先级: 低

Q5: 修订后迁移失败超阈值怎么办?
   场景: 作者重写了 40% 内容
   现状: 大量孤儿批注
   方案: 提示用户 "本书大幅改动, 建议作为新书处理"
   优先级: 中
```

---

## 12. 决策日志

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-04 | paragraph_id 采用三段式 `book:chapter:content` | 分层稳定，跨版本部分可识别 |
| 2026-04 | book_id 优先 ISBN，退化到作者+标题 | ISBN 是出版行业天然主键 |
| 2026-04 | chapter_fp 基于标题内容，不用序号 | 同书不同版章节可能重排 |
| 2026-04 | content_fp 归一化只压缩空白 | 保护专有名词大小写 |
| 2026-04 | 位置是后缀，不是 hash 成分 | 相同段落不同位置可区分；编辑靠 migration 补 |
| 2026-04 | 短段落（<20 字符）用 prev_text 补强 | 避免 "Yes." 这类碰撞 |
| 2026-04 | fuzzy migration 阈值 0.85 | 经验值，需实测调 |
| 2026-04 | MVP 用 SequenceMatcher，v2 换 embedding | 先跑起来再优化 |
| 2026-04 | EPUB CFI 作辅助字段，不作主 ID | CFI 是路径型，不稳定；但对外兼容有价值 |

---

## 附录：参考资料

- [EPUB 3 Canonical Fragment Identifier (CFI)](https://www.w3.org/TR/epub-cfi-11/) — 官方位置标识规范
- [Hypothesis Annotation Anchoring](https://web.hypothes.is/blog/fuzzy-anchoring/) — Web 批注的 fuzzy 锚点方案（"quote + prefix + suffix"）
- [BLAKE2 hash function](https://www.blake2.net/) — 选用 blake2b 而非 SHA256 的理由：更快、更现代
- [difflib.SequenceMatcher](https://docs.python.org/3/library/difflib.html) — MVP 相似度算法

---

## 更新日志

| 日期 | 变更 |
|------|------|
| 2026-04 | 初版起草，三段式 ID + fuzzy migration 方案 |
