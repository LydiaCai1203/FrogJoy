"""
概念提取核心逻辑 — 从 concept_service.py 迁移

三阶段流水线:
  Phase 0: 书籍分析 — 自动判断书的类型, 生成定制化抽取策略 (1 次 LLM)
  Phase 1: 全书逐章概念扫描 — 提取概念 + initial_definition (逐章 LLM)
  Phase 2: 跨章去重合并 (文本匹配 + embedding, 纯算法)
  Phase 3: 关键词匹配 — 找概念在全书中的出现位置 (纯算法, 零 LLM)
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable
from uuid import uuid4

import anthropic
import httpx
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import IndexedBook, IndexedParagraph, Concept, ConceptOccurrence


# ---------- Configuration ----------

MINIMAX_LLM_API_KEY = os.environ.get("MINIMAX_LLM_API_KEY", "")
MINIMAX_LLM_BASE_URL = os.environ.get("MINIMAX_LLM_BASE_URL", "https://api.minimaxi.com/anthropic")
MINIMAX_LLM_MODEL = os.environ.get("MINIMAX_LLM_MODEL", "MiniMax-M2.7")
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.environ.get("EMBEDDING_BASE_URL", "https://model-square.app.baizhi.cloud/v1/embeddings")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")


# ---------- DB helpers (替代 IndexService) ----------

def get_chapters(book_id: str, user_id: str) -> list[dict]:
    with get_db() as db:
        rows = (
            db.query(
                IndexedParagraph.chapter_idx,
                IndexedParagraph.chapter_title,
                IndexedParagraph.chapter_fp,
                func.count(IndexedParagraph.id).label("count"),
            )
            .filter_by(book_id=book_id, user_id=user_id)
            .group_by(
                IndexedParagraph.chapter_idx,
                IndexedParagraph.chapter_title,
                IndexedParagraph.chapter_fp,
            )
            .order_by(IndexedParagraph.chapter_idx)
            .all()
        )
        return [
            {
                "chapter_idx": r.chapter_idx,
                "chapter_title": r.chapter_title,
                "chapter_fp": r.chapter_fp,
                "paragraph_count": r.count,
            }
            for r in rows
        ]


def get_paragraphs(book_id: str, user_id: str, chapter_idx: int | None = None) -> list[dict]:
    with get_db() as db:
        q = db.query(IndexedParagraph).filter_by(book_id=book_id, user_id=user_id)
        if chapter_idx is not None:
            q = q.filter(IndexedParagraph.chapter_idx == chapter_idx)
        q = q.order_by(IndexedParagraph.chapter_idx, IndexedParagraph.para_idx_in_chapter)
        return [
            {
                "pid": p.id,
                "chapter_idx": p.chapter_idx,
                "chapter_title": p.chapter_title,
                "chapter_fp": p.chapter_fp,
                "para_idx": p.para_idx_in_chapter,
                "text": p.text,
            }
            for p in q.all()
        ]


def get_index_status(book_id: str, user_id: str) -> dict | None:
    with get_db() as db:
        record = db.query(IndexedBook).filter_by(book_id=book_id, user_id=user_id).first()
        if not record:
            return None
        return {"status": record.status, "concept_status": record.concept_status}


# ---------- 主流程 ----------

class ConceptExtractor:
    """
    概念提取执行器。

    progress_callback: (percent: int, text: str) -> None
    cancel_check: () -> bool, 返回 True 表示应取消
    """

    def __init__(
        self,
        book_id: str,
        user_id: str,
        rebuild: bool = False,
        progress_callback: Callable[[int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ):
        self.book_id = book_id
        self.user_id = user_id
        self.rebuild = rebuild
        self._progress = progress_callback or (lambda pct, txt: None)
        self._cancelled = cancel_check or (lambda: False)

    def run(self) -> dict:
        """
        全流程: Phase 0 → 1 → 2 → 3
        返回 {"concepts": int, "occurrences": int}
        """
        status = get_index_status(self.book_id, self.user_id)
        if not status or status["status"] != "parsed":
            raise ValueError("Index not ready, build index first")

        if not self.rebuild:
            with get_db() as db:
                record = db.query(IndexedBook).filter_by(
                    book_id=self.book_id, user_id=self.user_id
                ).first()
                if record and record.concept_status == "enriched":
                    return {"concepts": record.total_concepts, "occurrences": 0, "skipped": True}

        chapters = get_chapters(self.book_id, self.user_id)
        total_chapters = len(chapters)

        self._set_status("extracting")

        try:
            # Phase 0: 分析书籍类型
            self._progress(2, "Phase 0: 分析书籍类型...")
            strategy = self._phase0_analyze()
            logger.info(f"Phase 0 done: type={strategy.get('book_type')}")
            self._progress(5, f"Phase 0 完成: {strategy.get('book_type')}")

            # Phase 1: 逐章概念扫描
            raw_concepts = self._phase1_extract(strategy, total_chapters)
            logger.info(f"Phase 1 done: {len(raw_concepts)} raw concepts")

            # Phase 2: 去重合并
            self._progress(85, f"Phase 2: 去重合并 {len(raw_concepts)} 个概念...")
            concepts = self._phase2_deduplicate(raw_concepts, strategy)
            logger.info(f"Phase 2 done: {len(concepts)} merged concepts")
            self._progress(90, f"Phase 2 完成: {len(concepts)} 个概念")

            self._save_concepts(concepts)

            # Phase 3: 关键词匹配
            self._progress(92, "Phase 3: 关键词匹配...")
            occurrences = self._phase3_keyword_match()
            logger.info(f"Phase 3 done: {len(occurrences)} occurrences")
            self._progress(97, f"Phase 3 完成: {len(occurrences)} 处出现")

            self._save_occurrences(occurrences)
            self._update_stats()
            self._set_status("enriched")
            self._progress(100, "完成")

            return {"concepts": len(concepts), "occurrences": len(occurrences)}

        except InterruptedError as e:
            logger.info(f"Concept extraction cancelled: book={self.book_id}")
            self._set_status(None, str(e))
            raise

        except Exception as e:
            logger.exception(f"Concept extraction failed: book={self.book_id}")
            self._set_status("failed", str(e))
            raise

    # ===================================================================
    # Phase 0: 书籍分析
    # ===================================================================

    def _phase0_analyze(self) -> dict:
        chapters = get_chapters(self.book_id, self.user_id)
        toc = _build_toc(chapters)

        sample_texts = []
        for chapter in chapters:
            if len(sample_texts) >= 2:
                break
            paragraphs = get_paragraphs(
                self.book_id, self.user_id, chapter_idx=chapter["chapter_idx"]
            )
            if len(paragraphs) < 3:
                continue
            sample = "\n".join(p["text"] for p in paragraphs[:10])
            sample_texts.append(f"### {chapter['chapter_title']}\n{sample}")

        samples = "\n\n".join(sample_texts)

        prompt = f"""你是一个书籍分析专家。请根据以下信息分析这本书的类型和特点, 并生成概念抽取策略。

## 全书目录

{toc}

## 前两章采样

{samples}

## 任务

分析这本书, 输出严格 JSON:

{{
  "book_type": "书的类型 (如: 学术专著, 社科非虚构, 文学小说, 历史传记, 经济金融, 心理自助, 科普, 哲学 等)",
  "book_summary": "一句话概括这本书的内容和特点",
  "categories": ["适合这本书的概念分类列表, 3-6 个"],
  "extract_guidelines": "针对这本书, 什么样的内容应该被抽取为核心概念 (3-5 条具体规则)",
  "do_not_extract": "什么不应该抽取 (3-5 条具体规则)",
  "quantity_hint": "每 10 段大约抽取几个概念合适 (数字)"
}}

## 要求

- categories 要贴合这本书的内容
- extract_guidelines 要具体, 不要泛泛而谈
- 用中文回答

---

直接输出 JSON。"""

        try:
            result = _call_llm(
                system="你是一个书籍分析专家。",
                prompt=prompt,
                max_tokens=2000,
            )
            logger.info(f"Phase 0 strategy: {json.dumps(result, ensure_ascii=False)[:200]}")
            return result
        except Exception as e:
            logger.warning(f"Phase 0 failed, using default strategy: {e}")
            return _default_strategy()

    # ===================================================================
    # Phase 1: 逐章概念扫描
    # ===================================================================

    def _phase1_extract(self, strategy: dict, total_chapters: int) -> list[dict]:
        chapters = get_chapters(self.book_id, self.user_id)
        toc = _build_toc(chapters)

        all_concepts = []
        for i, chapter in enumerate(chapters):
            if self._cancelled():
                logger.info(f"Phase 1 cancelled at ch{i}/{total_chapters}")
                raise InterruptedError("用户取消了概念提取")

            paragraphs = get_paragraphs(
                self.book_id, self.user_id, chapter_idx=chapter["chapter_idx"]
            )
            if not paragraphs:
                continue

            if total_chapters > 0:
                pct = 5 + int(80 * i / total_chapters)
                self._progress(
                    pct,
                    f"Phase 1: {i+1}/{total_chapters} 章 '{chapter['chapter_title']}'"
                )

            try:
                result = _call_phase1_llm(toc, chapter, paragraphs, strategy)
                for concept in result:
                    concept["source_chapter_idx"] = chapter["chapter_idx"]
                    concept["source_chapter_title"] = chapter["chapter_title"]
                all_concepts.extend(result)
                logger.info(
                    f"Phase 1 ch{chapter['chapter_idx']}: "
                    f"{len(result)} concepts from '{chapter['chapter_title']}'"
                )
            except Exception as e:
                logger.warning(f"Phase 1 failed for ch{chapter['chapter_idx']}: {e}")
                continue

        return all_concepts

    # ===================================================================
    # Phase 2: 跨章去重
    # ===================================================================

    def _phase2_deduplicate(self, raw_concepts: list[dict], strategy: dict = None) -> list[dict]:
        merged = _text_merge(raw_concepts)

        if EMBEDDING_API_KEY:
            person_categories = {"person", "character"}
            non_person = [c for c in merged if c.get("category") not in person_categories]
            persons = [c for c in merged if c.get("category") in person_categories]
            non_person = _embedding_merge(non_person, threshold=0.85)
            merged = non_person + persons

        return merged

    # ===================================================================
    # Phase 3: 关键词匹配
    # ===================================================================

    def _phase3_keyword_match(self) -> list[dict]:
        with get_db() as db:
            concepts = db.query(Concept).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).all()
            paragraphs = (
                db.query(IndexedParagraph)
                .filter_by(book_id=self.book_id, user_id=self.user_id)
                .order_by(IndexedParagraph.chapter_idx, IndexedParagraph.para_idx_in_chapter)
                .all()
            )

        matchers = []
        for c in concepts:
            keywords = [c.term]
            if c.aliases:
                aliases = c.aliases if isinstance(c.aliases, list) else json.loads(c.aliases)
                keywords.extend(aliases)
            keywords = sorted(set(keywords), key=len, reverse=True)
            escaped = [re.escape(kw) for kw in keywords if kw.strip()]
            if not escaped:
                continue
            pattern = re.compile("|".join(escaped), re.IGNORECASE)
            matchers.append({
                "concept_id": c.id,
                "concept_term": c.term,
                "pattern": pattern,
                "keywords": keywords,
            })

        occurrences = []
        for para in paragraphs:
            text = para.text
            for m in matchers:
                match = m["pattern"].search(text)
                if match:
                    occurrences.append({
                        "concept_id": m["concept_id"],
                        "concept_term": m["concept_term"],
                        "pid": para.id,
                        "chapter_idx": para.chapter_idx,
                        "matched_text": match.group(0),
                    })

        logger.info(
            f"Phase 3 keyword match: {len(occurrences)} occurrences "
            f"from {len(paragraphs)} paragraphs × {len(matchers)} concepts"
        )
        return occurrences

    # ===================================================================
    # 存储
    # ===================================================================

    def _save_concepts(self, concepts):
        with get_db() as db:
            db.query(ConceptOccurrence).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).delete()
            db.query(Concept).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).delete()
            for c in concepts:
                db.add(Concept(
                    id=f"concept:{uuid4()}",
                    book_id=self.book_id,
                    user_id=self.user_id,
                    term=c["term"],
                    aliases=c["aliases"],
                    category=c["category"],
                    initial_definition=c.get("initial_definition", ""),
                ))
            db.commit()

    def _save_occurrences(self, occurrences):
        with get_db() as db:
            db.query(ConceptOccurrence).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).delete()

            valid_pids = {
                p.id for p in db.query(IndexedParagraph.id).filter_by(
                    book_id=self.book_id, user_id=self.user_id
                ).all()
            }

            skipped = 0
            for occ in occurrences:
                if occ["pid"] not in valid_pids:
                    skipped += 1
                    continue
                db.add(ConceptOccurrence(
                    id=f"occ:{uuid4()}",
                    concept_id=occ["concept_id"],
                    paragraph_id=occ["pid"],
                    user_id=self.user_id,
                    book_id=self.book_id,
                    chapter_idx=occ["chapter_idx"],
                    occurrence_type="mention",
                    matched_text=occ.get("matched_text"),
                    core_sentence=None,
                    reasoning=None,
                ))
            if skipped:
                logger.warning(f"Skipped {skipped} occurrences (invalid pid)")
            db.commit()

        self._mark_definitions()

    def _mark_definitions(self):
        with get_db() as db:
            concepts = db.query(Concept).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).all()
            for c in concepts:
                if not c.initial_definition:
                    continue
                first_occ = (
                    db.query(ConceptOccurrence)
                    .filter_by(concept_id=c.id)
                    .order_by(ConceptOccurrence.chapter_idx)
                    .first()
                )
                if first_occ:
                    first_occ.occurrence_type = "definition"
                    first_occ.core_sentence = c.initial_definition
            db.commit()

    def _update_stats(self):
        with get_db() as db:
            concepts = db.query(Concept).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).all()
            record = db.query(IndexedBook).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).first()

            for c in concepts:
                occs = db.query(ConceptOccurrence).filter_by(concept_id=c.id).all()
                c.total_occurrences = len(occs)
                c.chapter_count = len(set(o.chapter_idx for o in occs))
                c.scope = (
                    "book" if c.chapter_count >= record.total_chapters * 0.5
                    else "chapter"
                )

            record.total_concepts = len(concepts)
            db.commit()

    def _set_status(self, status, error=None):
        with get_db() as db:
            record = db.query(IndexedBook).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).first()
            if record:
                record.concept_status = status
                record.concept_error = error
                db.commit()


# ===================================================================
# 模块级工具函数 (无状态)
# ===================================================================

def _build_toc(chapters):
    return "\n".join(
        f'{ch["chapter_idx"]}. {ch["chapter_title"]}'
        for ch in chapters
    )


def _default_strategy() -> dict:
    return {
        "book_type": "非虚构",
        "book_summary": "",
        "categories": ["term", "term_custom", "person", "work", "theory"],
        "extract_guidelines": (
            "1. 作者特意定义、反复使用、有专门含义的术语\n"
            "2. 被作者引用其观点/研究/理论的人名\n"
            "3. 被引用的作品: 书籍、论文、理论流派"
        ),
        "do_not_extract": (
            "1. 常识词 / 过于泛泛的词\n"
            "2. 例子里偶然出现的人名\n"
            "3. 普通描述中出现的物品/动作"
        ),
        "quantity_hint": 5,
    }


def _call_llm(system, prompt, max_tokens=4000):
    client = anthropic.Anthropic(
        api_key=MINIMAX_LLM_API_KEY,
        base_url=MINIMAX_LLM_BASE_URL,
    )
    message = client.messages.create(
        model=MINIMAX_LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in message.content:
        if hasattr(block, "text"):
            text = block.text
            break
    return _parse_json(text)


def _parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def _call_phase1_llm(toc, chapter, paragraphs, strategy):
    paragraphs_text = "\n\n".join(
        f'[P{p["para_idx"]:02d}|{p["pid"]}]\n{p["text"]}'
        for p in paragraphs
    )

    categories = ", ".join(strategy.get("categories", ["term", "person", "theme"]))
    quantity = strategy.get("quantity_hint", 5)

    prompt = f"""你是一个精确的书籍概念抽取助手, 服务于"书的索引库"(Book Language Server).

## 书籍信息

类型: {strategy.get("book_type", "未知")}
概述: {strategy.get("book_summary", "")}

## 全书目录

{toc}

## 当前章节: {chapter["chapter_title"]}

## 抽取规则

应该抽取:
{strategy.get("extract_guidelines", "")}

不要抽取:
{strategy.get("do_not_extract", "")}

## 分类: {categories}

## 输出: 严格 JSON

{{
  "concepts": [
    {{
      "term": "规范名",
      "aliases": ["别名1"],
      "category": "分类",
      "initial_definition": "用作者原文中的话解释这个概念, 1-2 句, 控制在 100 字内"
    }}
  ]
}}

## 要求

- aliases 只收录原文出现过的变体, 不要自行翻译
- initial_definition 必须尽量使用作者的原话, 不要自己编
- 宁少勿多, 每 10 段 ≤ {quantity} 个

## 章节文本

{paragraphs_text}

---

直接输出 JSON。"""

    return _call_llm(
        system="你是一个精确的书籍概念抽取助手。",
        prompt=prompt,
        max_tokens=4000,
    )["concepts"]


def _text_merge(raw_concepts: list[dict]) -> list[dict]:
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
            if not existing.get("initial_definition") and c.get("initial_definition"):
                existing["initial_definition"] = c["initial_definition"]
                existing["source_chapter_idx"] = c.get("source_chapter_idx")
                existing["source_chapter_title"] = c.get("source_chapter_title")
            existing.setdefault("all_definitions", [])
            if c.get("initial_definition"):
                existing["all_definitions"].append({
                    "text": c["initial_definition"],
                    "chapter_idx": c.get("source_chapter_idx"),
                    "chapter_title": c.get("source_chapter_title"),
                })
            existing.setdefault("source_chapters", [])
            if c.get("source_chapter_idx") not in existing["source_chapters"]:
                existing["source_chapters"].append(c["source_chapter_idx"])
        else:
            entry = {
                "term": term,
                "aliases": c.get("aliases", []),
                "category": c.get("category", "term"),
                "initial_definition": c.get("initial_definition", ""),
                "source_chapter_idx": c.get("source_chapter_idx"),
                "source_chapter_title": c.get("source_chapter_title"),
                "source_chapters": [c.get("source_chapter_idx")],
                "all_definitions": [],
            }
            if c.get("initial_definition"):
                entry["all_definitions"].append({
                    "text": c["initial_definition"],
                    "chapter_idx": c.get("source_chapter_idx"),
                    "chapter_title": c.get("source_chapter_title"),
                })
            merged[term_lower] = entry
            for alias in c.get("aliases", []):
                alias_map[alias.strip().lower()] = term_lower

    return list(merged.values())


def _embedding_merge(concepts: list[dict], threshold: float = 0.85) -> list[dict]:
    if len(concepts) <= 1:
        return concepts

    terms = [c["term"] for c in concepts]
    embeddings = _get_embeddings(terms)
    if not embeddings or len(embeddings) != len(concepts):
        logger.warning("Embedding call failed, skip embedding merge")
        return concepts

    merged_into = {}
    for i in range(len(concepts)):
        if i in merged_into:
            continue
        for j in range(i + 1, len(concepts)):
            if j in merged_into:
                continue
            sim = _cosine_similarity(embeddings[i], embeddings[j])
            if sim >= threshold:
                logger.info(
                    f"Embedding merge: '{concepts[i]['term']}' + "
                    f"'{concepts[j]['term']}' (sim={sim:.3f})"
                )
                merged_into[j] = i

    result = []
    for i, c in enumerate(concepts):
        if i in merged_into:
            target = concepts[merged_into[i]]
            new_aliases = set(target.get("aliases", []))
            new_aliases.add(c["term"])
            new_aliases.update(c.get("aliases", []))
            new_aliases.discard(target["term"])
            target["aliases"] = list(new_aliases)
            target.setdefault("all_definitions", [])
            target["all_definitions"].extend(c.get("all_definitions", []))
            target.setdefault("source_chapters", [])
            for ch in c.get("source_chapters", []):
                if ch not in target["source_chapters"]:
                    target["source_chapters"].append(ch)
        else:
            result.append(c)

    return result


def _get_embeddings(texts: list[str]) -> list[list[float]] | None:
    if not EMBEDDING_API_KEY:
        return None
    try:
        results = []
        for text in texts:
            resp = httpx.post(
                EMBEDDING_BASE_URL,
                headers={
                    "Authorization": f"Bearer {EMBEDDING_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"model": EMBEDDING_MODEL, "input": text},
                timeout=30,
            )
            resp.raise_for_status()
            results.append(resp.json()["data"][0]["embedding"])
        return results
    except Exception as e:
        logger.warning(f"Embedding API error: {e}")
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
