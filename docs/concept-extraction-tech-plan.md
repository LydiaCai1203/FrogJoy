# 概念提取技术方案

> 基于 `concept-extraction-and-hover-design.md` 的实现规划
>
> 日期：2026-04-21
> 更新：适配重构后的 shared/ 架构

---

## 0. 现状

项目已完成重构：
- **shared 层**：`shared/models/`、`shared/schemas/`、`shared/config.py`、`shared/database.py` 抽出作为 epub-tts-backend 和 admin-backend 的公共基础
- **router 拆分**：15 个独立 router，统一 `/api` 前缀注册
- **service 包化**：复杂 service（tts、ai）拆为子包
- **migration**：当前最新 `016_refactor_preferences_and_ai`

已实现 LSP v0：
- `shared/models/index.py`：`IndexedBook` / `IndexedParagraph`
- `app/services/index_service.py`：EPUB 解析 → 段落入库
- `app/routers/index.py`：索引 CRUD API
- 后台任务模式：FastAPI `BackgroundTasks`

本方案新增**概念层**，不改动现有表结构。

---

## 1. 整体流程

```
POST /api/books/{book_id}/index          (已有, 不改)
  → EPUB 解析 → indexed_paragraphs 入库
  → status: parsed

POST /api/books/{book_id}/concepts/build (新增)
  → 前置检查: index status == parsed
  → 后台执行 3 个阶段:
      Phase 1: 全书逐章概念扫描 (LLM)
      Phase 2: 跨章去重合并 (纯算法)
      Phase 3: 全书段落 occurrence 标注 (LLM)
  → 写入 concepts + concept_occurrences
  → concept_status: enriched
```

---

## 2. 数据库

### 2.1 新增 ORM: `shared/models/concept.py`

```python
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey, Index, func
from shared.models import Base


class Concept(Base):
    __tablename__ = "concepts"

    id          = Column(String, primary_key=True)       # concept:{uuid4}
    book_id     = Column(String, ForeignKey("books.id"), nullable=False)
    user_id     = Column(String, ForeignKey("users.id"), nullable=False)

    term        = Column(String, nullable=False)          # 规范名
    aliases     = Column(JSON, nullable=False, default=[]) # 别名列表
    category    = Column(String, nullable=False)          # term/term_custom/person/work/theory

    # 频次统计 (Phase 3 后回填)
    total_occurrences = Column(Integer, nullable=False, default=0)
    chapter_count     = Column(Integer, nullable=False, default=0)
    scope             = Column(String, nullable=False, default="chapter")  # book / chapter

    created_at  = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_concepts_user_book", "user_id", "book_id"),
    )


class ConceptOccurrence(Base):
    __tablename__ = "concept_occurrences"

    id               = Column(String, primary_key=True)    # occ:{uuid4}
    concept_id       = Column(String, ForeignKey("concepts.id"), nullable=False)
    paragraph_id     = Column(String, ForeignKey("indexed_paragraphs.id"), nullable=False)
    user_id          = Column(String, nullable=False)
    book_id          = Column(String, nullable=False)
    chapter_idx      = Column(Integer, nullable=False)

    occurrence_type  = Column(String, nullable=False)      # definition/refinement/mention
    matched_text     = Column(Text, nullable=True)         # 匹配的原文片段
    core_sentence    = Column(Text, nullable=True)         # 弹窗展示用核心句
    reasoning        = Column(Text, nullable=True)         # LLM 标注理由

    created_at       = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_occ_user_book", "user_id", "book_id"),
        Index("idx_occ_concept", "concept_id"),
        Index("idx_occ_paragraph", "paragraph_id"),
        Index("idx_occ_user_book_chapter", "user_id", "book_id", "chapter_idx"),
    )
```

### 2.2 注册到 `shared/models/__init__.py`

```python
from shared.models.concept import Concept, ConceptOccurrence

__all__ = [
    ...,
    "Concept", "ConceptOccurrence",
]
```

### 2.3 IndexedBook 扩展字段

`shared/models/index.py` 的 `IndexedBook` 新增：

```python
concept_status = Column(String, nullable=True)   # None/extracting/enriched/failed
concept_error  = Column(Text, nullable=True)
total_concepts = Column(Integer, nullable=False, default=0)
```

### 2.4 Migration: `017_add_concept_tables.py`

```python
"""Add concept extraction tables: concepts + concept_occurrences

Revision ID: 017_add_concept_tables
Revises: 016_refactor_preferences_and_ai
"""
from alembic import op
import sqlalchemy as sa

revision = "017_add_concept_tables"
down_revision = "016_refactor_preferences_and_ai"

def upgrade() -> None:
    # --- concepts ---
    op.create_table(
        "concepts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("term", sa.String(), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("total_occurrences", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chapter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scope", sa.String(), nullable=False, server_default="chapter"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_concepts_user_book", "concepts", ["user_id", "book_id"])

    # --- concept_occurrences ---
    op.create_table(
        "concept_occurrences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("concept_id", sa.String(), nullable=False),
        sa.Column("paragraph_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("chapter_idx", sa.Integer(), nullable=False),
        sa.Column("occurrence_type", sa.String(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("core_sentence", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"]),
        sa.ForeignKeyConstraint(["paragraph_id"], ["indexed_paragraphs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_occ_user_book", "concept_occurrences", ["user_id", "book_id"])
    op.create_index("idx_occ_concept", "concept_occurrences", ["concept_id"])
    op.create_index("idx_occ_paragraph", "concept_occurrences", ["paragraph_id"])
    op.create_index("idx_occ_user_book_chapter", "concept_occurrences",
                    ["user_id", "book_id", "chapter_idx"])

    # --- indexed_books 扩展 ---
    op.add_column("indexed_books", sa.Column("concept_status", sa.String(), nullable=True))
    op.add_column("indexed_books", sa.Column("concept_error", sa.Text(), nullable=True))
    op.add_column("indexed_books", sa.Column("total_concepts", sa.Integer(),
                  nullable=False, server_default="0"))

def downgrade() -> None:
    op.drop_column("indexed_books", "total_concepts")
    op.drop_column("indexed_books", "concept_error")
    op.drop_column("indexed_books", "concept_status")
    op.drop_index("idx_occ_user_book_chapter", table_name="concept_occurrences")
    op.drop_index("idx_occ_paragraph", table_name="concept_occurrences")
    op.drop_index("idx_occ_concept", table_name="concept_occurrences")
    op.drop_index("idx_occ_user_book", table_name="concept_occurrences")
    op.drop_table("concept_occurrences")
    op.drop_index("idx_concepts_user_book", table_name="concepts")
    op.drop_table("concepts")
```

---

## 3. 配置

### 3.1 `shared/config.py` 新增

```python
class Settings(BaseSettings):
    ...
    # Minimax LLM (概念提取)
    minimax_llm_api_key: str = ""
    minimax_llm_base_url: str = "https://api.minimaxi.com/anthropic"
    minimax_llm_model: str = "MiniMax-M2.7"
```

注：已有 `minimax_base_url` 是 TTS 用的（`https://api.minimaxi.com`），LLM 接口走 Anthropic 兼容路径，用独立字段区分。

### 3.2 `.env` 新增

```
MINIMAX_LLM_API_KEY=sk-cp-...
MINIMAX_LLM_BASE_URL=https://api.minimaxi.com/anthropic
```

---

## 4. Service: `app/services/concept_service.py`

```python
"""
概念提取 Service —— Book Language Server 的概念层

三阶段流水线:
  Phase 1: 全书逐章概念扫描 (LLM)
  Phase 2: 跨章去重合并 (纯算法)
  Phase 3: 全书段落 occurrence 标注 (LLM)
"""
from __future__ import annotations

import json
from uuid import uuid4

import anthropic
from loguru import logger

from shared.config import settings
from shared.database import get_db
from shared.models import IndexedBook, Concept, ConceptOccurrence
from app.services.index_service import IndexService


class ConceptService:

    # --- Build (主入口) ---

    @classmethod
    def build_concepts(cls, book_id: str, user_id: str, rebuild: bool = False):
        """全流程: Phase 1 → 2 → 3"""
        # 前置检查
        status = IndexService.get_status(book_id, user_id)
        if not status or status["status"] != "parsed":
            raise ValueError("Index not ready, build index first")

        if not rebuild:
            with get_db() as db:
                record = db.query(IndexedBook).filter_by(
                    book_id=book_id, user_id=user_id
                ).first()
                if record and record.concept_status == "enriched":
                    return

        cls._set_status(book_id, user_id, "extracting")
        try:
            raw_concepts = cls._phase1_extract(book_id, user_id)
            logger.info(f"Phase 1 done: {len(raw_concepts)} raw concepts")

            concepts = cls._phase2_deduplicate(raw_concepts)
            logger.info(f"Phase 2 done: {len(concepts)} merged concepts")

            cls._save_concepts(book_id, user_id, concepts)

            occurrences = cls._phase3_annotate(book_id, user_id, concepts)
            logger.info(f"Phase 3 done: {len(occurrences)} occurrences")

            cls._save_occurrences(book_id, user_id, occurrences)
            cls._update_stats(book_id, user_id)
            cls._set_status(book_id, user_id, "enriched")

        except Exception as e:
            logger.exception(f"Concept extraction failed: book={book_id}")
            cls._set_status(book_id, user_id, "failed", str(e))
            raise

    # --- Phase 1: 逐章概念扫描 ---

    @classmethod
    def _phase1_extract(cls, book_id: str, user_id: str) -> list[dict]:
        chapters = IndexService.get_chapters(book_id, user_id)
        toc = cls._build_toc(chapters)

        all_concepts = []
        for chapter in chapters:
            paragraphs = IndexService.get_paragraphs(
                book_id, user_id, chapter_idx=chapter["chapter_idx"]
            )
            if not paragraphs:
                continue

            try:
                result = cls._call_phase1_llm(toc, chapter, paragraphs)
                for concept in result:
                    concept["source_chapter_idx"] = chapter["chapter_idx"]
                all_concepts.extend(result)
                logger.info(
                    f"Phase 1 ch{chapter['chapter_idx']}: "
                    f"{len(result)} concepts from '{chapter['chapter_title']}'"
                )
            except Exception as e:
                logger.warning(
                    f"Phase 1 failed for ch{chapter['chapter_idx']}: {e}"
                )
                continue  # 单章失败不中断全书

        return all_concepts

    @classmethod
    def _call_phase1_llm(cls, toc, chapter, paragraphs):
        paragraphs_text = "\n\n".join(
            f'[P{p["para_idx"]:02d}|{p["pid"]}]\n{p["text"]}'
            for p in paragraphs
        )

        prompt = f"""你是一个精确的学术术语抽取助手, 服务于"书的索引库"(Book Language Server).

## 全书目录 (供判断概念全书重要性)

{toc}

## 当前章节: {chapter["chapter_title"]}

## 什么是"核心概念"

必须抽取:
1. 作者特意定义、反复使用、有专门含义的术语 (包括作者自创的)
2. 被作者引用其观点/研究/理论的人名
3. 被引用的作品: 书籍、论文、理论流派

不要抽取:
1. 常识词 / 过于泛泛的词
2. 例子里偶然出现的人名
3. 普通描述中出现的物品/动作

## 分类: term / term_custom / person / work / theory

## 输出: 严格 JSON

{{
  "concepts": [
    {{
      "term": "规范名",
      "aliases": ["别名1"],
      "category": "term",
      "reasoning": "一句话说明"
    }}
  ]
}}

aliases 只收录原文出现过的变体, 不要自行翻译。
宁少勿多, 每 10 段 ≤ 5 个。

## 章节文本

{paragraphs_text}

---

直接输出 JSON。"""

        return cls._call_llm(
            system="你是一个精确的学术术语抽取助手。",
            prompt=prompt,
            max_tokens=4000,
        )["concepts"]

    # --- Phase 2: 跨章去重 ---

    @classmethod
    def _phase2_deduplicate(cls, raw_concepts: list[dict]) -> list[dict]:
        merged = {}
        alias_map = {}

        for c in raw_concepts:
            term = c["term"].strip()
            term_lower = term.lower()

            existing_key = None
            if term_lower in merged:
                existing_key = term_lower
            elif term_lower in alias_map:
                existing_key = alias_map[term_lower]
            else:
                for alias in c.get("aliases", []):
                    al = alias.strip().lower()
                    if al in merged:
                        existing_key = al
                        break
                    if al in alias_map:
                        existing_key = alias_map[al]
                        break

            if existing_key:
                existing = merged[existing_key]
                new_aliases = set(existing.get("aliases", []))
                new_aliases.update(c.get("aliases", []))
                new_aliases.discard(existing["term"])
                existing["aliases"] = list(new_aliases)
                existing.setdefault("source_chapters", [])
                if c.get("source_chapter_idx") not in existing["source_chapters"]:
                    existing["source_chapters"].append(c["source_chapter_idx"])
            else:
                merged[term_lower] = {
                    "term": term,
                    "aliases": c.get("aliases", []),
                    "category": c.get("category", "term"),
                    "reasoning": c.get("reasoning", ""),
                    "source_chapters": [c.get("source_chapter_idx")],
                }
                for alias in c.get("aliases", []):
                    alias_map[alias.strip().lower()] = term_lower

        return list(merged.values())

    # --- Phase 3: 全书段落标注 ---

    @classmethod
    def _phase3_annotate(cls, book_id, user_id, concepts):
        chapters = IndexService.get_chapters(book_id, user_id)
        concept_summary = cls._build_concept_summary(concepts)

        all_occurrences = []
        for chapter in chapters:
            paragraphs = IndexService.get_paragraphs(
                book_id, user_id, chapter_idx=chapter["chapter_idx"]
            )
            if not paragraphs:
                continue

            try:
                result = cls._call_phase3_llm(concept_summary, chapter, paragraphs)
                for occ in result:
                    occ["chapter_idx"] = chapter["chapter_idx"]
                all_occurrences.extend(result)
                logger.info(
                    f"Phase 3 ch{chapter['chapter_idx']}: "
                    f"{len(result)} occurrences"
                )
            except Exception as e:
                logger.warning(
                    f"Phase 3 failed for ch{chapter['chapter_idx']}: {e}"
                )
                continue

        return all_occurrences

    @classmethod
    def _call_phase3_llm(cls, concept_summary, chapter, paragraphs):
        paragraphs_text = "\n\n".join(
            f'[P{p["para_idx"]:02d}|{p["pid"]}]\n{p["text"]}'
            for p in paragraphs
        )

        prompt = f"""## 已知概念列表

{concept_summary}

## 当前章节: {chapter["chapter_title"]}

## 任务

对以下每个段落:
1. 判断该段落是否提到了上述概念（通过术语名、别名、或同义表述）
2. 对每次出现，标注类型:
   - `definition`: 作者在此处定义或解释这个概念
   - `refinement`: 作者在此处深化、补充、举例说明
   - `mention`: 顺带提及，未展开
3. 提取 core_sentence: 如果是 definition 或 refinement, 提取作者原文中最核心的 1-2 句话（用于悬浮弹窗展示, 控制在 100 字内）
4. 没提到任何概念的段落跳过

## 输出: 严格 JSON

{{
  "occurrences": [
    {{
      "pid": "段落ID (用 [P##|pid] 中的 pid)",
      "concept_term": "概念规范名",
      "occurrence_type": "definition|refinement|mention",
      "matched_text": "段落中匹配到概念的原文片段 (10-30字)",
      "core_sentence": "作者解释该概念的核心句 (仅 definition/refinement, 100字内)",
      "reasoning": "一句话说明为什么是这个类型"
    }}
  ]
}}

## 重要原则

- 一个段落可出现多个概念, 每个单独一条
- definition 应很少——通常一个概念全书只有 1-2 处真正在定义
- refinement 比 definition 多但也不泛滥
- mention 最常见
- core_sentence 只在 definition 和 refinement 时提供, mention 留空

## 段落文本

{paragraphs_text}

---

直接输出 JSON。"""

        return cls._call_llm(
            system="你是一个精确的文本分析助手，服务于书的索引库。",
            prompt=prompt,
            max_tokens=8000,
        )["occurrences"]

    # --- 存储 ---

    @classmethod
    def _save_concepts(cls, book_id, user_id, concepts):
        with get_db() as db:
            db.query(ConceptOccurrence).filter_by(
                book_id=book_id, user_id=user_id
            ).delete()
            db.query(Concept).filter_by(
                book_id=book_id, user_id=user_id
            ).delete()
            for c in concepts:
                db.add(Concept(
                    id=f"concept:{uuid4()}",
                    book_id=book_id,
                    user_id=user_id,
                    term=c["term"],
                    aliases=c["aliases"],
                    category=c["category"],
                ))
            db.commit()

    @classmethod
    def _save_occurrences(cls, book_id, user_id, occurrences):
        with get_db() as db:
            db.query(ConceptOccurrence).filter_by(
                book_id=book_id, user_id=user_id
            ).delete()

            concepts = db.query(Concept).filter_by(
                book_id=book_id, user_id=user_id
            ).all()
            term_to_id = {c.term: c.id for c in concepts}

            # 校验 pid 存在性
            from shared.models import IndexedParagraph
            valid_pids = {
                p.id for p in db.query(IndexedParagraph.id).filter_by(
                    book_id=book_id, user_id=user_id
                ).all()
            }

            skipped = 0
            for occ in occurrences:
                concept_id = term_to_id.get(occ["concept_term"])
                if not concept_id:
                    skipped += 1
                    continue
                if occ["pid"] not in valid_pids:
                    logger.warning(f"Invalid pid from LLM: {occ['pid']}")
                    skipped += 1
                    continue
                db.add(ConceptOccurrence(
                    id=f"occ:{uuid4()}",
                    concept_id=concept_id,
                    paragraph_id=occ["pid"],
                    user_id=user_id,
                    book_id=book_id,
                    chapter_idx=occ["chapter_idx"],
                    occurrence_type=occ["occurrence_type"],
                    matched_text=occ.get("matched_text"),
                    core_sentence=occ.get("core_sentence"),
                    reasoning=occ.get("reasoning"),
                ))
            if skipped:
                logger.warning(f"Skipped {skipped} occurrences (invalid concept/pid)")
            db.commit()

    @classmethod
    def _update_stats(cls, book_id, user_id):
        with get_db() as db:
            concepts = db.query(Concept).filter_by(
                book_id=book_id, user_id=user_id
            ).all()
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()

            for c in concepts:
                occs = db.query(ConceptOccurrence).filter_by(concept_id=c.id).all()
                c.total_occurrences = len(occs)
                c.chapter_count = len(set(o.chapter_idx for o in occs))
                c.scope = "book" if c.chapter_count >= record.total_chapters * 0.5 else "chapter"

            record.total_concepts = len(concepts)
            db.commit()

    # --- 查询 (供 router 调用) ---

    @classmethod
    def get_status(cls, book_id, user_id) -> dict | None:
        with get_db() as db:
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()
            if not record:
                return None
            return {
                "concept_status": record.concept_status,
                "concept_error": record.concept_error,
                "total_concepts": record.total_concepts,
            }

    @classmethod
    def get_concepts(cls, book_id, user_id) -> list[dict]:
        with get_db() as db:
            concepts = (
                db.query(Concept)
                .filter_by(book_id=book_id, user_id=user_id)
                .order_by(Concept.total_occurrences.desc())
                .all()
            )
            return [
                {
                    "concept_id": c.id,
                    "term": c.term,
                    "aliases": c.aliases,
                    "category": c.category,
                    "total_occurrences": c.total_occurrences,
                    "chapter_count": c.chapter_count,
                    "scope": c.scope,
                }
                for c in concepts
            ]

    @classmethod
    def get_concept_detail(cls, concept_id, user_id) -> dict | None:
        with get_db() as db:
            c = db.query(Concept).filter_by(id=concept_id).first()
            if not c or c.user_id != user_id:
                return None
            occs = (
                db.query(ConceptOccurrence)
                .filter_by(concept_id=concept_id)
                .order_by(ConceptOccurrence.chapter_idx)
                .all()
            )
            return {
                "concept_id": c.id,
                "term": c.term,
                "aliases": c.aliases,
                "category": c.category,
                "total_occurrences": c.total_occurrences,
                "chapter_count": c.chapter_count,
                "scope": c.scope,
                "occurrences": [
                    {
                        "pid": o.paragraph_id,
                        "chapter_idx": o.chapter_idx,
                        "occurrence_type": o.occurrence_type,
                        "matched_text": o.matched_text,
                        "core_sentence": o.core_sentence,
                    }
                    for o in occs
                ],
            }

    @classmethod
    def get_chapter_annotations(cls, book_id, user_id, chapter_idx) -> list[dict]:
        """
        返回某章的概念角标数据 (前端渲染用)。

        逻辑:
          1. 查该章所有 occurrences
          2. 按 concept 分组, 每个取首次出现段落
          3. 弹窗内容: 只取 chapter_idx <= 当前章 的 definition/refinement
          4. badge 按首次出现顺序编号
          5. 只返回有 definition/refinement 的概念 (mention-only 不标角标)
        """
        with get_db() as db:
            # 该章所有 occurrences
            chapter_occs = (
                db.query(ConceptOccurrence)
                .filter_by(book_id=book_id, user_id=user_id, chapter_idx=chapter_idx)
                .all()
            )

            # 按 concept 分组, 找首次出现
            concept_first = {}  # concept_id → first para_idx
            from shared.models import IndexedParagraph
            for occ in chapter_occs:
                if occ.concept_id not in concept_first:
                    para = db.query(IndexedParagraph).filter_by(id=occ.paragraph_id).first()
                    concept_first[occ.concept_id] = para.para_idx_in_chapter if para else 999

            # 只保留有 definition/refinement 的概念
            concepts_with_explanation = set()
            all_def_ref = (
                db.query(ConceptOccurrence)
                .filter(
                    ConceptOccurrence.book_id == book_id,
                    ConceptOccurrence.user_id == user_id,
                    ConceptOccurrence.chapter_idx <= chapter_idx,
                    ConceptOccurrence.occurrence_type.in_(["definition", "refinement"]),
                )
                .all()
            )
            for occ in all_def_ref:
                concepts_with_explanation.add(occ.concept_id)

            # 过滤: 该章出现过 + 全书有 definition/refinement
            valid_concepts = {
                cid for cid in concept_first
                if cid in concepts_with_explanation
            }

            # 按首次出现顺序编号
            sorted_concepts = sorted(valid_concepts, key=lambda cid: concept_first[cid])

            annotations = []
            for badge_num, concept_id in enumerate(sorted_concepts, 1):
                c = db.query(Concept).filter_by(id=concept_id).first()
                # 弹窗: 取 chapter_idx <= 当前章 的 definition/refinement, 最多 2 条
                explanations = (
                    db.query(ConceptOccurrence)
                    .filter(
                        ConceptOccurrence.concept_id == concept_id,
                        ConceptOccurrence.chapter_idx <= chapter_idx,
                        ConceptOccurrence.occurrence_type.in_(["definition", "refinement"]),
                        ConceptOccurrence.core_sentence.isnot(None),
                    )
                    .order_by(ConceptOccurrence.chapter_idx)
                    .limit(2)
                    .all()
                )
                # 首次出现的 pid
                first_occ = min(
                    [o for o in chapter_occs if o.concept_id == concept_id],
                    key=lambda o: concept_first.get(o.concept_id, 0),
                )
                annotations.append({
                    "concept_id": c.id,
                    "term": c.term,
                    "badge_number": badge_num,
                    "first_pid_in_chapter": first_occ.paragraph_id,
                    "popover": {
                        "term": c.term,
                        "explanations": [
                            {
                                "core_sentence": e.core_sentence,
                                "chapter_idx": e.chapter_idx,
                                "pid": e.paragraph_id,
                            }
                            for e in explanations
                        ],
                    },
                })

            return annotations

    @classmethod
    def delete_concepts(cls, book_id, user_id) -> bool:
        with get_db() as db:
            db.query(ConceptOccurrence).filter_by(
                book_id=book_id, user_id=user_id
            ).delete()
            deleted = db.query(Concept).filter_by(
                book_id=book_id, user_id=user_id
            ).delete()
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()
            if record:
                record.concept_status = None
                record.concept_error = None
                record.total_concepts = 0
            db.commit()
            return deleted > 0

    # --- 内部工具 ---

    @classmethod
    def _set_status(cls, book_id, user_id, status, error=None):
        with get_db() as db:
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()
            if record:
                record.concept_status = status
                record.concept_error = error
                db.commit()

    @classmethod
    def _get_client(cls):
        return anthropic.Anthropic(
            api_key=settings.minimax_llm_api_key,
            base_url=settings.minimax_llm_base_url,
        )

    @classmethod
    def _call_llm(cls, system, prompt, max_tokens=4000):
        client = cls._get_client()
        message = client.messages.create(
            model=settings.minimax_llm_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in message.content:
            if hasattr(block, "text"):
                text = block.text
                break
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)

    @classmethod
    def _build_toc(cls, chapters):
        return "\n".join(
            f'{ch["chapter_idx"]}. {ch["chapter_title"]} ({ch["paragraph_count"]}段)'
            for ch in chapters
        )

    @classmethod
    def _build_concept_summary(cls, concepts):
        lines = []
        for c in concepts:
            aliases = ", ".join(c["aliases"]) if c["aliases"] else "无"
            lines.append(f'- {c["term"]} (别名: {aliases}) [{c["category"]}]')
        return "\n".join(lines)
```

---

## 5. Router: `app/routers/concepts.py`

```python
"""
概念提取 API

端点:
  POST   /api/books/{book_id}/concepts/build
  GET    /api/books/{book_id}/concepts/status
  GET    /api/books/{book_id}/concepts
  GET    /api/books/{book_id}/concepts/by-chapter/{chapter_idx}
  GET    /api/books/{book_id}/concepts/{concept_id}
  DELETE /api/books/{book_id}/concepts
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from loguru import logger

from app.middleware.auth import get_current_user
from app.services.concept_service import ConceptService

router = APIRouter(prefix="/books", tags=["concepts"])


@router.post("/{book_id}/concepts/build")
async def build_concepts(
    book_id: str,
    background: BackgroundTasks,
    rebuild: bool = Query(False),
    user_id: str = Depends(get_current_user),
):
    status = ConceptService.get_status(book_id, user_id)
    if status and status["concept_status"] == "enriched" and not rebuild:
        return {"message": "already enriched", **status}
    if status and status["concept_status"] == "extracting":
        return {"message": "already extracting", **status}

    background.add_task(_build_bg, book_id=book_id, user_id=user_id, rebuild=rebuild)
    return {"message": "concept extraction started", "concept_status": "extracting"}


def _build_bg(book_id, user_id, rebuild):
    try:
        ConceptService.build_concepts(book_id, user_id, rebuild)
    except Exception:
        logger.exception("Concept extraction crashed")


@router.get("/{book_id}/concepts/status")
async def get_status(book_id: str, user_id: str = Depends(get_current_user)):
    status = ConceptService.get_status(book_id, user_id)
    if not status:
        return {"concept_status": None}
    return status


@router.get("/{book_id}/concepts")
async def list_concepts(book_id: str, user_id: str = Depends(get_current_user)):
    return {"concepts": ConceptService.get_concepts(book_id, user_id)}


@router.get("/{book_id}/concepts/by-chapter/{chapter_idx}")
async def get_chapter_annotations(
    book_id: str,
    chapter_idx: int,
    user_id: str = Depends(get_current_user),
):
    annotations = ConceptService.get_chapter_annotations(
        book_id, user_id, chapter_idx
    )
    return {"book_id": book_id, "chapter_idx": chapter_idx, "annotations": annotations}


@router.get("/{book_id}/concepts/{concept_id}")
async def get_concept_detail(
    book_id: str,
    concept_id: str,
    user_id: str = Depends(get_current_user),
):
    detail = ConceptService.get_concept_detail(concept_id, user_id)
    if not detail:
        raise HTTPException(404, "Concept not found")
    return detail


@router.delete("/{book_id}/concepts")
async def delete_concepts(book_id: str, user_id: str = Depends(get_current_user)):
    deleted = ConceptService.delete_concepts(book_id, user_id)
    if not deleted:
        raise HTTPException(404, "No concepts found")
    return {"message": "concepts deleted"}
```

### 注册到 `app/main.py`

```python
from app.routers.concepts import router as concepts_router
...
app.include_router(concepts_router, prefix="/api")
```

---

## 6. 文件清单

```
epub-tts-backend/
├── alembic/versions/
│   └── 017_add_concept_tables.py           # NEW: migration
├── shared/
│   ├── models/
│   │   ├── concept.py                      # NEW: Concept, ConceptOccurrence
│   │   ├── index.py                        # MODIFY: +concept_status 等字段
│   │   └── __init__.py                     # MODIFY: +Concept, ConceptOccurrence
│   └── config.py                           # MODIFY: +minimax_llm_* 配置
├── app/
│   ├── services/
│   │   └── concept_service.py              # NEW: ConceptService
│   ├── routers/
│   │   └── concepts.py                     # NEW: REST API
│   └── main.py                             # MODIFY: +concepts_router
└── .env                                    # MODIFY: +MINIMAX_LLM_API_KEY
```

---

## 7. 执行计划

### Step 1: 基础设施
- [ ] `shared/models/concept.py` — ORM models
- [ ] `shared/models/index.py` — IndexedBook 加 concept_status 等字段
- [ ] `shared/models/__init__.py` — 注册新 models
- [ ] `shared/config.py` — minimax_llm_* 配置
- [ ] `017_add_concept_tables.py` — migration
- [ ] `.env` — API key

### Step 2: ConceptService
- [ ] `app/services/concept_service.py` — 完整 service（Phase 1-3 + 查询 + 存储）

### Step 3: API
- [ ] `app/routers/concepts.py` — 6 个端点
- [ ] `app/main.py` — 注册 router

### Step 4: 端到端验证
- [ ] 启动服务，跑 migration
- [ ] 用已索引的书调 `POST /concepts/build`
- [ ] 检查 `GET /concepts/by-chapter/{idx}` 返回的角标和弹窗数据

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| LLM 输出 JSON 格式错误 | 个别章节标注失败 | 单章失败 continue，不中断全书 |
| LLM 返回的 pid 不在 DB 中 | occurrence 丢失 | pid 校验 + 跳过 + log |
| 概念过多导致 prompt 超长 | 某章标注不完整 | 按概念数拆分多次调用 |
| 全书扫描耗时较长 | 用户等待 | 后台任务 + concept_status 轮询 |
| 去重漏合并 (同义但 alias 未覆盖) | 概念重复 | v2 可加 embedding 相似度 |

---

## 9. 成本估算

10 章 500 段的书，Minimax M2.7：

| 阶段 | LLM 调用次数 | 输入 tokens | 输出 tokens |
|------|-------------|------------|------------|
| Phase 1 (概念扫描) | 10 | ~120K | ~20K |
| Phase 2 (去重) | 0 | 0 | 0 |
| Phase 3 (标注) | 10 | ~150K | ~50K |
| **合计** | **20** | **~270K** | **~70K** |
