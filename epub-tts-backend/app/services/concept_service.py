"""
概念提取 Service —— Book Language Server 的概念层

三阶段流水线:
  Phase 0: 书籍分析 — 自动判断书的类型, 生成定制化抽取策略 (1 次 LLM)
  Phase 1: 全书逐章概念扫描 — 提取概念 + initial_definition (逐章 LLM)
  Phase 2: 跨章去重合并 (文本匹配 + embedding, 纯算法)
  Phase 3: 关键词匹配 — 找概念在全书中的出现位置 (纯算法, 零 LLM)

设计文档:
  - docs/concept-extraction-and-hover-design.md
  - docs/concept-extraction-tech-plan.md
"""
from __future__ import annotations

import json
import re
from uuid import uuid4

import anthropic
import httpx
from loguru import logger

from shared.config import settings
from shared.database import get_db
from shared.models import IndexedBook, IndexedParagraph, Concept, ConceptOccurrence
from app.services.index_service import IndexService


class ConceptService:

    # ===================================================================
    # Build (主入口)
    # ===================================================================

    @classmethod
    def build_concepts(cls, book_id: str, user_id: str, rebuild: bool = False):
        """全流程: Phase 0 → 1 → 2 → 3"""
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
            # Phase 0: 分析书籍类型
            strategy = cls._phase0_analyze(book_id, user_id)
            logger.info(f"Phase 0 done: type={strategy.get('book_type')}")

            # Phase 1: 逐章概念扫描 (含 initial_definition)
            raw_concepts = cls._phase1_extract(book_id, user_id, strategy)
            logger.info(f"Phase 1 done: {len(raw_concepts)} raw concepts")

            # Phase 2: 去重合并
            concepts = cls._phase2_deduplicate(raw_concepts, strategy)
            logger.info(f"Phase 2 done: {len(concepts)} merged concepts")

            cls._save_concepts(book_id, user_id, concepts)

            # Phase 3: 关键词匹配出现位置 (纯算法)
            occurrences = cls._phase3_keyword_match(book_id, user_id)
            logger.info(f"Phase 3 done: {len(occurrences)} occurrences")

            cls._save_occurrences(book_id, user_id, occurrences)
            cls._update_stats(book_id, user_id)
            cls._set_status(book_id, user_id, "enriched")

        except Exception as e:
            logger.exception(f"Concept extraction failed: book={book_id}")
            cls._set_status(book_id, user_id, "failed", str(e))
            raise

    # ===================================================================
    # Phase 0: 书籍分析
    # ===================================================================

    @classmethod
    def _phase0_analyze(cls, book_id: str, user_id: str) -> dict:
        chapters = IndexService.get_chapters(book_id, user_id)
        toc = cls._build_toc(chapters)

        # 采样前两个有内容的章节
        sample_texts = []
        for chapter in chapters:
            if len(sample_texts) >= 2:
                break
            paragraphs = IndexService.get_paragraphs(
                book_id, user_id, chapter_idx=chapter["chapter_idx"]
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
            result = cls._call_llm(
                system="你是一个书籍分析专家。",
                prompt=prompt,
                max_tokens=2000,
            )
            logger.info(f"Phase 0 strategy: {json.dumps(result, ensure_ascii=False)[:200]}")
            return result
        except Exception as e:
            logger.warning(f"Phase 0 failed, using default strategy: {e}")
            return cls._default_strategy()

    @classmethod
    def _default_strategy(cls) -> dict:
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

    # ===================================================================
    # Phase 1: 逐章概念扫描 (含 initial_definition)
    # ===================================================================

    @classmethod
    def _phase1_extract(cls, book_id: str, user_id: str, strategy: dict) -> list[dict]:
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
                result = cls._call_phase1_llm(toc, chapter, paragraphs, strategy)
                for concept in result:
                    concept["source_chapter_idx"] = chapter["chapter_idx"]
                    concept["source_chapter_title"] = chapter["chapter_title"]
                all_concepts.extend(result)
                logger.info(
                    f"Phase 1 ch{chapter['chapter_idx']}: "
                    f"{len(result)} concepts from '{chapter['chapter_title']}'"
                )
            except Exception as e:
                logger.warning(
                    f"Phase 1 failed for ch{chapter['chapter_idx']}: {e}"
                )
                continue

        return all_concepts

    @classmethod
    def _call_phase1_llm(cls, toc, chapter, paragraphs, strategy):
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

        return cls._call_llm(
            system="你是一个精确的书籍概念抽取助手。",
            prompt=prompt,
            max_tokens=4000,
        )["concepts"]

    # ===================================================================
    # Phase 2: 跨章去重 (文本匹配 + embedding)
    # ===================================================================

    @classmethod
    def _phase2_deduplicate(cls, raw_concepts: list[dict], strategy: dict = None) -> list[dict]:
        # 第一轮: 文本匹配
        merged = cls._text_merge(raw_concepts)

        # 第二轮: embedding (人物类跳过)
        if settings.embedding_api_key:
            person_categories = {"person", "character"}
            non_person = [c for c in merged if c.get("category") not in person_categories]
            persons = [c for c in merged if c.get("category") in person_categories]
            non_person = cls._embedding_merge(non_person, threshold=0.85)
            merged = non_person + persons

        return merged

    @classmethod
    def _text_merge(cls, raw_concepts: list[dict]) -> list[dict]:
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
                # 保留最早的 definition
                if not existing.get("initial_definition") and c.get("initial_definition"):
                    existing["initial_definition"] = c["initial_definition"]
                    existing["source_chapter_idx"] = c.get("source_chapter_idx")
                    existing["source_chapter_title"] = c.get("source_chapter_title")
                # 收集所有 definitions (用于弹窗多条解释)
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

    @classmethod
    def _embedding_merge(cls, concepts: list[dict], threshold: float = 0.85) -> list[dict]:
        if len(concepts) <= 1:
            return concepts

        terms = [c["term"] for c in concepts]
        embeddings = cls._get_embeddings(terms)
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
                sim = cls._cosine_similarity(embeddings[i], embeddings[j])
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
                # 合并 definitions
                target.setdefault("all_definitions", [])
                target["all_definitions"].extend(c.get("all_definitions", []))
                target.setdefault("source_chapters", [])
                for ch in c.get("source_chapters", []):
                    if ch not in target["source_chapters"]:
                        target["source_chapters"].append(ch)
            else:
                result.append(c)

        return result

    # ===================================================================
    # Phase 3: 关键词匹配出现位置 (纯算法, 零 LLM)
    # ===================================================================

    @classmethod
    def _phase3_keyword_match(cls, book_id: str, user_id: str) -> list[dict]:
        """
        用概念的 term + aliases 做关键词匹配, 找出每个概念在全书中的出现位置。
        纯文本匹配, 不调 LLM。
        """
        with get_db() as db:
            concepts = db.query(Concept).filter_by(
                book_id=book_id, user_id=user_id
            ).all()
            paragraphs = (
                db.query(IndexedParagraph)
                .filter_by(book_id=book_id, user_id=user_id)
                .order_by(IndexedParagraph.chapter_idx, IndexedParagraph.para_idx_in_chapter)
                .all()
            )

        # 构建匹配模式: concept_id → (term, [aliases], compiled_pattern)
        matchers = []
        for c in concepts:
            keywords = [c.term]
            if c.aliases:
                aliases = c.aliases if isinstance(c.aliases, list) else json.loads(c.aliases)
                keywords.extend(aliases)
            # 按长度降序排列, 优先匹配长的
            keywords = sorted(set(keywords), key=len, reverse=True)
            # 构建正则: 匹配任意一个关键词 (忽略大小写)
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
                    initial_definition=c.get("initial_definition", ""),
                ))
            db.commit()

    @classmethod
    def _save_occurrences(cls, book_id, user_id, occurrences):
        with get_db() as db:
            db.query(ConceptOccurrence).filter_by(
                book_id=book_id, user_id=user_id
            ).delete()

            valid_pids = {
                p.id for p in db.query(IndexedParagraph.id).filter_by(
                    book_id=book_id, user_id=user_id
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
                    user_id=user_id,
                    book_id=book_id,
                    chapter_idx=occ["chapter_idx"],
                    occurrence_type="mention",  # 关键词匹配默认 mention
                    matched_text=occ.get("matched_text"),
                    core_sentence=None,
                    reasoning=None,
                ))
            if skipped:
                logger.warning(f"Skipped {skipped} occurrences (invalid pid)")
            db.commit()

        # 标记 definition: 概念的 initial_definition 来源段落
        cls._mark_definitions(book_id, user_id)

    @classmethod
    def _mark_definitions(cls, book_id, user_id):
        """
        概念首次出现的 occurrence 标记为 definition,
        core_sentence 填入 Concept.initial_definition。
        """
        with get_db() as db:
            concepts = db.query(Concept).filter_by(
                book_id=book_id, user_id=user_id
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
                c.scope = (
                    "book" if c.chapter_count >= record.total_chapters * 0.5
                    else "chapter"
                )

            record.total_concepts = len(concepts)
            db.commit()

    # ===================================================================
    # 查询 (供 router 调用)
    # ===================================================================

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
                    "initial_definition": c.initial_definition,
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

        弹窗内容来自 Phase 1 的 initial_definition (存在 Concept 表)。
        只展示 chapter_idx <= 当前章 的概念 (防剧透)。
        """
        with get_db() as db:
            # 该章所有 occurrences
            chapter_occs = (
                db.query(ConceptOccurrence)
                .filter_by(
                    book_id=book_id, user_id=user_id, chapter_idx=chapter_idx
                )
                .all()
            )
            if not chapter_occs:
                return []

            # 按 concept 分组, 找首次出现的段落位置
            concept_first_para = {}
            for occ in chapter_occs:
                if occ.concept_id not in concept_first_para:
                    para = db.query(IndexedParagraph).filter_by(
                        id=occ.paragraph_id
                    ).first()
                    concept_first_para[occ.concept_id] = (
                        para.para_idx_in_chapter if para else 999
                    )

            # 只标注有 initial_definition 的概念 (有内容可弹窗的才值得标角标)
            concepts_with_def = set()
            for cid in concept_first_para:
                c = db.query(Concept).filter_by(id=cid).first()
                if c and c.initial_definition:
                    concepts_with_def.add(cid)

            if not concepts_with_def:
                return []

            # 按首次出现顺序编号
            sorted_concepts = sorted(
                concepts_with_def,
                key=lambda cid: concept_first_para[cid]
            )

            annotations = []
            for badge_num, concept_id in enumerate(sorted_concepts, 1):
                c = db.query(Concept).filter_by(id=concept_id).first()
                if not c:
                    continue

                # 首次出现的 pid
                first_occ = min(
                    (o for o in chapter_occs if o.concept_id == concept_id),
                    key=lambda o: concept_first_para.get(o.concept_id, 0),
                )

                annotations.append({
                    "concept_id": c.id,
                    "term": c.term,
                    "badge_number": badge_num,
                    "first_pid_in_chapter": first_occ.paragraph_id,
                    "popover": {
                        "term": c.term,
                        "initial_definition": c.initial_definition,
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

    # ===================================================================
    # 内部工具: LLM
    # ===================================================================

    @classmethod
    def _call_llm(cls, system, prompt, max_tokens=4000):
        client = anthropic.Anthropic(
            api_key=settings.minimax_llm_api_key,
            base_url=settings.minimax_llm_base_url,
        )
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
        return cls._parse_json(text)

    @classmethod
    def _parse_json(cls, text: str):
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)

    # ===================================================================
    # 内部工具: Embedding
    # ===================================================================

    @classmethod
    def _get_embeddings(cls, texts: list[str]) -> list[list[float]] | None:
        if not settings.embedding_api_key:
            return None
        try:
            results = []
            for text in texts:
                resp = httpx.post(
                    settings.embedding_base_url,
                    headers={
                        "Authorization": f"Bearer {settings.embedding_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": settings.embedding_model, "input": text},
                    timeout=30,
                )
                resp.raise_for_status()
                results.append(resp.json()["data"][0]["embedding"])
            return results
        except Exception as e:
            logger.warning(f"Embedding API error: {e}")
            return None

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ===================================================================
    # 内部工具: 文本构建
    # ===================================================================

    @classmethod
    def _build_toc(cls, chapters):
        return "\n".join(
            f'{ch["chapter_idx"]}. {ch["chapter_title"]}'
            for ch in chapters
        )

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
