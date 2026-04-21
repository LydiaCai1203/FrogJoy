"""
概念提取 Service —— Book Language Server 的概念层

三阶段流水线:
  Phase 1: 全书逐章概念扫描 (LLM)
  Phase 2: 跨章去重合并 (文本匹配 + embedding 相似度)
  Phase 3: 全书段落 occurrence 标注 (LLM)

设计文档:
  - docs/concept-extraction-and-hover-design.md
  - docs/concept-extraction-tech-plan.md
"""
from __future__ import annotations

import json
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
        """全流程: Phase 1 → 2 → 3"""
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

    # ===================================================================
    # Phase 1: 逐章概念扫描
    # ===================================================================

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
                continue

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

    # ===================================================================
    # Phase 2: 跨章去重 (文本匹配 + embedding)
    # ===================================================================

    @classmethod
    def _phase2_deduplicate(cls, raw_concepts: list[dict]) -> list[dict]:
        """
        合并策略:
          1. 完全同名 → 合并, aliases 取并集
          2. 别名匹配 → A 的 term 出现在 B 的 aliases → 合并
          3. embedding 相似度 > 0.85 → 合并
        """
        # 第一轮: 文本匹配
        merged = cls._text_merge(raw_concepts)

        # 第二轮: embedding 相似度 (如果配置了 embedding)
        if settings.embedding_api_key:
            merged = cls._embedding_merge(merged, threshold=0.85)

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

    @classmethod
    def _embedding_merge(cls, concepts: list[dict], threshold: float = 0.85) -> list[dict]:
        """用 embedding 相似度合并语义相近但文本不同的概念。"""
        if len(concepts) <= 1:
            return concepts

        terms = [c["term"] for c in concepts]
        embeddings = cls._get_embeddings(terms)
        if not embeddings or len(embeddings) != len(concepts):
            logger.warning("Embedding call failed or size mismatch, skip embedding merge")
            return concepts

        # 找高相似度对
        merged_into = {}  # idx → merged_into_idx
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

        # 执行合并
        result = []
        for i, c in enumerate(concepts):
            if i in merged_into:
                target = concepts[merged_into[i]]
                new_aliases = set(target.get("aliases", []))
                new_aliases.add(c["term"])
                new_aliases.update(c.get("aliases", []))
                new_aliases.discard(target["term"])
                target["aliases"] = list(new_aliases)
                target.setdefault("source_chapters", [])
                for ch in c.get("source_chapters", []):
                    if ch not in target["source_chapters"]:
                        target["source_chapters"].append(ch)
            else:
                result.append(c)

        return result

    # ===================================================================
    # Phase 3: 全书段落标注
    # ===================================================================

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
          5. 只返回有 definition/refinement 的概念
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

            # 全书中有 definition/refinement 的概念 (截止到当前章)
            concepts_with_explanation = set()
            def_ref_occs = (
                db.query(ConceptOccurrence)
                .filter(
                    ConceptOccurrence.book_id == book_id,
                    ConceptOccurrence.user_id == user_id,
                    ConceptOccurrence.chapter_idx <= chapter_idx,
                    ConceptOccurrence.occurrence_type.in_(
                        ["definition", "refinement"]
                    ),
                )
                .all()
            )
            for occ in def_ref_occs:
                concepts_with_explanation.add(occ.concept_id)

            # 过滤: 该章出现过 + 有 definition/refinement
            valid_concepts = {
                cid for cid in concept_first_para
                if cid in concepts_with_explanation
            }
            if not valid_concepts:
                return []

            # 按首次出现顺序编号
            sorted_concepts = sorted(
                valid_concepts, key=lambda cid: concept_first_para[cid]
            )

            annotations = []
            for badge_num, concept_id in enumerate(sorted_concepts, 1):
                c = db.query(Concept).filter_by(id=concept_id).first()
                if not c:
                    continue

                # 弹窗: chapter_idx <= 当前章 的 def/ref, 最多 2 条
                explanations = (
                    db.query(ConceptOccurrence)
                    .filter(
                        ConceptOccurrence.concept_id == concept_id,
                        ConceptOccurrence.chapter_idx <= chapter_idx,
                        ConceptOccurrence.occurrence_type.in_(
                            ["definition", "refinement"]
                        ),
                        ConceptOccurrence.core_sentence.isnot(None),
                    )
                    .order_by(ConceptOccurrence.chapter_idx)
                    .limit(2)
                    .all()
                )

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
        """批量获取文本的 embedding 向量。"""
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
                    json={
                        "model": settings.embedding_model,
                        "input": text,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                results.append(data["data"][0]["embedding"])
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
