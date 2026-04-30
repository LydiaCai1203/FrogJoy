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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
from uuid import uuid4

import httpx
from loguru import logger

from services.llm_provider import LLMConfig, LLMService
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import (
    IndexedBook, IndexedParagraph, Concept, ConceptOccurrence, ConceptEvidence,
)


# ---------- Configuration (env var fallback) ----------

CONCEPT_LLM_API_KEY = os.environ.get("CONCEPT_LLM_API_KEY", "")
CONCEPT_LLM_BASE_URL = os.environ.get("CONCEPT_LLM_BASE_URL", "https://api.minimaxi.com/anthropic")
CONCEPT_LLM_MODEL = os.environ.get("CONCEPT_LLM_MODEL", "MiniMax-M2.7")
CONCEPT_EMBED_API_KEY = os.environ.get("CONCEPT_EMBED_API_KEY", "")
CONCEPT_EMBED_BASE_URL = os.environ.get("CONCEPT_EMBED_BASE_URL", "https://model-square.app.baizhi.cloud/v1/embeddings")
CONCEPT_EMBED_MODEL = os.environ.get("CONCEPT_EMBED_MODEL", "bge-m3")


# ---------- LLM Config (from backend via A2A) ----------

from services.llm_provider import LLMConfig


def _get_llm_config(ai_config: dict | LLMConfig | None, embedding_config: dict | None) -> tuple[LLMConfig, dict]:
    """从 A2A payload 解析 LLM 和 Embedding 配置，无配置时用 env var 兜底."""
    if isinstance(ai_config, LLMConfig):
        llm = ai_config
    else:
        llm = LLMConfig(
            provider_type=(ai_config or {}).get("provider_type", "anthropic"),
            base_url=(ai_config or {}).get("base_url") or CONCEPT_LLM_BASE_URL,
            api_key=(ai_config or {}).get("api_key") or CONCEPT_LLM_API_KEY,
            model=(ai_config or {}).get("model") or CONCEPT_LLM_MODEL,
        )
    emb = {
        "base_url": (embedding_config or {}).get("base_url") or CONCEPT_EMBED_BASE_URL,
        "api_key": (embedding_config or {}).get("api_key") or CONCEPT_EMBED_API_KEY,
        "model": (embedding_config or {}).get("model") or CONCEPT_EMBED_MODEL,
    }
    return llm, emb


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
        ai_config: dict | None = None,
        embedding_config: dict | None = None,
    ):
        self.book_id = book_id
        self.user_id = user_id
        self.rebuild = rebuild
        self._progress = progress_callback or (lambda pct, txt: None)
        self._cancelled = cancel_check or (lambda: False)
        self._llm_config, self._emb_config = _get_llm_config(ai_config, embedding_config)

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
            self._progress(83, f"Phase 2: 去重合并 {len(raw_concepts)} 个概念...")
            concepts = self._phase2_deduplicate(raw_concepts, strategy)
            logger.info(f"Phase 2 done: {len(concepts)} merged concepts")

            # Phase 2.5: 释义合成 (基于 evidence 句子 + 书籍背景)
            self._progress(86, f"Phase 2.5: 释义合成 {len(concepts)} 个概念...")
            self._phase2_5_synthesize_definitions(concepts, strategy)
            self._progress(90, f"Phase 2.5 完成")

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
  "quantity_hint": "每 10 段大约抽取几个概念合适 (数字)",
  "cultural_context_guidelines": "这本书中, 作者默认读者已知但未做解释的文化背景知识有哪些类型 (如政党立场、社会阶层、宗教习俗、政治制度、历史事件的影响等), 列出 2-4 条具体类型"
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
                config=self._llm_config,
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

        # 预加载所有章节段落, 避免线程内并发访问 DB session
        chapter_paragraphs = {}
        for chapter in chapters:
            paragraphs = get_paragraphs(
                self.book_id, self.user_id, chapter_idx=chapter["chapter_idx"]
            )
            if paragraphs:
                chapter_paragraphs[chapter["chapter_idx"]] = paragraphs

        all_concepts = []
        done_count = 0
        done_lock = threading.Lock()

        def _process_chapter(i: int, chapter: dict) -> list[dict]:
            nonlocal done_count
            paragraphs = chapter_paragraphs.get(chapter["chapter_idx"])
            if not paragraphs:
                return []
            try:
                raw = _call_phase1_llm(toc, chapter, paragraphs, strategy, self._llm_config)
                # 服务端硬校验: quote 必须 verbatim, term/alias 必须在 quote 里
                validated = _validate_evidence(raw, paragraphs)
                # 给每条 evidence 打上 chapter_idx (Phase 2 合并/Phase 3 补全要用)
                for concept in validated:
                    concept["source_chapter_idx"] = chapter["chapter_idx"]
                    concept["source_chapter_title"] = chapter["chapter_title"]
                    for ev in concept["evidence"]:
                        ev["chapter_idx"] = chapter["chapter_idx"]
                logger.info(
                    f"Phase 1 ch{chapter['chapter_idx']}: "
                    f"raw={len(raw)} validated={len(validated)} "
                    f"from '{chapter['chapter_title']}'"
                )
                return validated
            except Exception as e:
                logger.warning(f"Phase 1 failed for ch{chapter['chapter_idx']}: {e}")
                return []
            finally:
                with done_lock:
                    done_count += 1
                    pct = 5 + int(80 * done_count / max(total_chapters, 1))
                    self._progress(
                        pct,
                        f"Phase 1: {done_count}/{total_chapters} 章完成"
                    )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for i, chapter in enumerate(chapters):
                if self._cancelled():
                    logger.info(f"Phase 1 cancelled before submitting ch{i}")
                    raise InterruptedError("用户取消了概念提取")
                future = executor.submit(_process_chapter, i, chapter)
                futures[future] = chapter

            for future in as_completed(futures):
                if self._cancelled():
                    logger.info("Phase 1 cancelled during collection")
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise InterruptedError("用户取消了概念提取")
                all_concepts.extend(future.result())

        return all_concepts

    # ===================================================================
    # Phase 2: 跨章去重
    # ===================================================================

    def _phase2_deduplicate(self, raw_concepts: list[dict], strategy: dict = None) -> list[dict]:
        # Step A: 完全同名同别名直接合并 (无歧义)
        merged = _text_merge(raw_concepts)

        # Step B: embedding 产候选对 + LLM 当裁判
        # 旧版 embedding 直接 ≥0.85 自动 merge, 会把"社会流动"<->"向上流动"
        # 这种相关但不同的概念错误压成 alias. 现在 embedding 只筛候选,
        # LLM 判定 SAME / PARENT_CHILD / UNRELATED.
        if CONCEPT_EMBED_API_KEY:
            person_categories = {"person", "character"}
            non_person = [c for c in merged if c.get("category") not in person_categories]
            persons = [c for c in merged if c.get("category") in person_categories]
            non_person = _llm_concept_linker(non_person, sim_threshold=0.75, top_k=3, config=self._llm_config, emb_config=self._emb_config)
            merged = non_person + persons

        return merged

    # ===================================================================
    # Phase 2.5: 释义合成
    # ===================================================================

    def _phase2_5_synthesize_definitions(
        self, concepts: list[dict], strategy: dict, batch_size: int = 5
    ) -> None:
        """为每个概念生成 initial_definition.

        给 LLM 的内容:
          - 书籍背景 (book_type, book_summary)
          - 概念 term + aliases + category + parent (如有)
          - 跨章 evidence 中的句子 (带章号)
        LLM 任务:
          - 普通术语/理论: 综合句子提炼"它是什么"
          - 专有名词 (人名/地名/作品名): 结合书籍背景 + 常识告诉读者
            "这是谁/在哪/什么作品, 在书中扮演什么角色"
        """
        if not concepts:
            return

        term_to_concept = {c["term"]: c for c in concepts}
        total = len(concepts)
        total_batches = (total + batch_size - 1) // batch_size
        done = 0
        ok_count = 0
        for batch_idx, chunk_start in enumerate(range(0, total, batch_size), 1):
            chunk = concepts[chunk_start:chunk_start + batch_size]
            t0 = time.monotonic()
            try:
                results = _synthesize_definitions_batch(chunk, strategy, self._llm_config)
                batch_ok = 0
                for term, defn in results.items():
                    if term in term_to_concept and defn:
                        term_to_concept[term]["initial_definition"] = defn
                        ok_count += 1
                        batch_ok += 1
                elapsed = time.monotonic() - t0
                logger.info(
                    f"Phase 2.5 batch {batch_idx}/{total_batches}: "
                    f"{batch_ok}/{len(chunk)} ok ({elapsed:.1f}s)"
                )
            except Exception as e:
                elapsed = time.monotonic() - t0
                logger.warning(
                    f"Phase 2.5 batch {batch_idx}/{total_batches} failed "
                    f"after {elapsed:.1f}s: {e}"
                )
            done += len(chunk)
            self._progress(
                86 + int(4 * done / max(total, 1)),  # 86-90 区间
                f"Phase 2.5: {done}/{total}",
            )
        logger.info(f"Phase 2.5 done: synthesized {ok_count}/{total} definitions")

    # ===================================================================
    # Phase 3: 关键词匹配
    # ===================================================================

    def _phase3_keyword_match(self) -> list[dict]:
        """补全弱出现 (mention) — definition/refinement 已由 evidence 承载.

        仲裁规则:
          1. 跨概念按 keyword 长度降序匹配, 长串先占位 (避免"流动"抢"社会流动"的位置)
          2. 已被 evidence 占用的 (pid, span) 不重复出 mention
          3. 任意已 claim 的 span 不可被新 match 覆盖 (含部分重叠)
        """
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
            evidence_rows = (
                db.query(
                    ConceptEvidence.concept_id,
                    ConceptEvidence.paragraph_id,
                    ConceptEvidence.char_offset,
                    ConceptEvidence.char_length,
                )
                .filter_by(book_id=self.book_id, user_id=self.user_id)
                .all()
            )

        # evidence 的 spans 按 pid 索引, Phase 3 不能再在这些位置出 mention
        evidence_spans: dict[str, list[tuple[int, int, str]]] = {}
        for ev in evidence_rows:
            evidence_spans.setdefault(ev.paragraph_id, []).append(
                (ev.char_offset, ev.char_offset + ev.char_length, ev.concept_id)
            )

        # 跨概念建 matcher: 每条 (concept_id, keyword), 按 length 降序排
        matchers: list[dict] = []
        for c in concepts:
            keywords = [c.term]
            if c.aliases:
                aliases = c.aliases if isinstance(c.aliases, list) else json.loads(c.aliases)
                keywords.extend(aliases)
            for kw in set(keywords):
                if not kw or not kw.strip():
                    continue
                matchers.append({
                    "concept_id": c.id,
                    "keyword": kw,
                    "pattern": re.compile(re.escape(kw), re.IGNORECASE),
                    "length": len(kw),
                })
        matchers.sort(key=lambda m: m["length"], reverse=True)

        def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
            return a[0] < b[1] and b[0] < a[1]

        occurrences: list[dict] = []
        for para in paragraphs:
            text = para.text
            # 把 evidence span 作为初始 claim, mention 不可与之重叠
            claimed: list[tuple[int, int]] = [
                (s, e) for s, e, _ in evidence_spans.get(para.id, [])
            ]
            for m in matchers:
                for match in m["pattern"].finditer(text):
                    span = (match.start(), match.end())
                    if any(_overlaps(span, c) for c in claimed):
                        continue
                    claimed.append(span)
                    occurrences.append({
                        "concept_id": m["concept_id"],
                        "pid": para.id,
                        "chapter_idx": para.chapter_idx,
                        "matched_text": match.group(0),
                    })

        logger.info(
            f"Phase 3 keyword match: {len(occurrences)} mention occurrences "
            f"from {len(paragraphs)} paragraphs × {len(matchers)} matchers "
            f"(evidence span suppressed)"
        )
        return occurrences

    # ===================================================================
    # 存储
    # ===================================================================

    def _save_concepts(self, concepts):
        with get_db() as db:
            db.query(ConceptEvidence).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).delete()
            db.query(ConceptOccurrence).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).delete()
            db.query(Concept).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).delete()

            valid_pids = {
                p.id for p in db.query(IndexedParagraph.id).filter_by(
                    book_id=self.book_id, user_id=self.user_id
                ).all()
            }

            # Pass 1: 写 Concept (parent_concept_id 先空), 同时记录 term -> id 映射
            term_to_id: dict[str, str] = {}
            evidence_dropped = 0
            for c in concepts:
                cid = f"concept:{uuid4()}"
                term_to_id[c["term"]] = cid
                db.add(Concept(
                    id=cid,
                    book_id=self.book_id,
                    user_id=self.user_id,
                    term=c["term"],
                    aliases=c["aliases"],
                    category=c["category"],
                    initial_definition=c.get("initial_definition", ""),
                    parent_concept_id=None,
                ))
                # 持久化 evidence (Phase 1 已 verbatim 校验过)
                for ev in c.get("evidence", []):
                    if ev["pid"] not in valid_pids:
                        evidence_dropped += 1
                        continue
                    db.add(ConceptEvidence(
                        id=f"ev:{uuid4()}",
                        concept_id=cid,
                        paragraph_id=ev["pid"],
                        user_id=self.user_id,
                        book_id=self.book_id,
                        chapter_idx=ev["chapter_idx"],
                        quote=ev["quote"],
                        role=ev["role"],
                        char_offset=ev["char_offset"],
                        char_length=ev["char_length"],
                    ))
            db.flush()

            # Pass 2: 解析 _parent_term -> parent_concept_id
            for c in concepts:
                parent_term = c.get("_parent_term")
                if not parent_term:
                    continue
                cid = term_to_id.get(c["term"])
                pid = term_to_id.get(parent_term)
                if not cid or not pid or cid == pid:
                    continue
                db.query(Concept).filter_by(id=cid).update(
                    {"parent_concept_id": pid}
                )

            if evidence_dropped:
                logger.warning(f"Dropped {evidence_dropped} evidence rows (invalid pid)")
            db.commit()

    def _save_occurrences(self, occurrences):
        """Phase 3 输出全部 mention 类型 (definition/refinement 由 evidence 承载)."""
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

    def _update_stats(self):
        """统计 evidence + occurrence 之和 (二者各管 definition/refinement 与 mention)."""
        with get_db() as db:
            concepts = db.query(Concept).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).all()
            record = db.query(IndexedBook).filter_by(
                book_id=self.book_id, user_id=self.user_id
            ).first()

            for c in concepts:
                occ_chapters = {
                    row.chapter_idx
                    for row in db.query(ConceptOccurrence.chapter_idx)
                    .filter_by(concept_id=c.id)
                    .all()
                }
                ev_chapters = {
                    row.chapter_idx
                    for row in db.query(ConceptEvidence.chapter_idx)
                    .filter_by(concept_id=c.id)
                    .all()
                }
                occ_count = (
                    db.query(ConceptOccurrence).filter_by(concept_id=c.id).count()
                )
                ev_count = (
                    db.query(ConceptEvidence).filter_by(concept_id=c.id).count()
                )
                c.total_occurrences = occ_count + ev_count
                c.chapter_count = len(occ_chapters | ev_chapters)
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


def _extract_sentence(text: str, keyword: str) -> str | None:
    """从段落中提取包含 keyword 的句子。"""
    sentences = re.split(r'(?<=[。！？.!?])', text)
    for s in sentences:
        if keyword in s and s.strip():
            return s.strip()
    return None


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
        "cultural_context_guidelines": "政党立场、社会阶层、宗教习俗、历史事件影响等作者默认读者已知但未做解释的文化背景",
    }


def _call_llm(system, prompt, max_tokens=4000, max_retries=3, config: LLMConfig | None = None):
    cfg = config or _get_llm_config(None, None)[0]
    service = LLMService(cfg)
    last_error = None
    text = ""
    for attempt in range(max_retries):
        try:
            text = service.chat_once(system, prompt, max_tokens)
            if not text or not text.strip():
                logger.warning(
                    f"LLM returned empty text: model={cfg.model} "
                    f"provider={cfg.provider_type} prompt_chars={len(prompt)}"
                )
            return _parse_json(text)
        except json.JSONDecodeError as e:
            raw_preview = (text[:500] + "…") if len(text) > 500 else text
            logger.warning(
                f"LLM JSON parse failed (attempt {attempt+1}/{max_retries}): {e}\n"
                f"  raw[{len(text)}chars]={raw_preview!r}"
            )
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                logger.error(f"LLM call failed after {max_retries} attempts: {e}")
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"LLM API error (attempt {attempt+1}/{max_retries}): "
                f"status={e.response.status_code} body={e.response.text!r} err={e}"
            )
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                logger.error(f"LLM call failed after {max_retries} attempts: {e}")
        except httpx.HTTPError as e:
            logger.warning(
                f"LLM transport error (attempt {attempt+1}/{max_retries}): "
                f"{type(e).__name__}: {e}"
            )
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                logger.error(f"LLM call failed after {max_retries} attempts: {e}")
    raise last_error


def _parse_json(text: str):
    """容忍 LLM 加散文/空字符串/```代码块的稳健 JSON 解析."""
    text = (text or "").strip()
    if not text:
        raise json.JSONDecodeError("LLM returned empty text", text, 0)
    # 剥 ``` ``` 围栏
    if text.startswith("```"):
        lines = text.split("\n")
        lines_no_fence = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines_no_fence).strip()
    # 退一步: 抓第一个 { 到最后一个 } 之间的子串再试 (防散文前缀/后缀)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            return json.loads(text[first:last + 1])
        raise


def _call_phase1_llm(toc, chapter, paragraphs, strategy, config: LLMConfig | None = None):
    paragraphs_text = "\n\n".join(
        f'[P{p["para_idx"]:02d}]\n{p["text"]}'
        for p in paragraphs
    )

    cat_list = list(strategy.get("categories", ["term", "person", "theme"]))
    if "cultural_context" not in cat_list:
        cat_list.append("cultural_context")
    categories = ", ".join(cat_list)
    quantity = strategy.get("quantity_hint", 5)
    cultural_guidelines = strategy.get("cultural_context_guidelines", "")

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
      "term": "规范名 (作者原文中最常用的形式)",
      "aliases": ["原文中实际出现的其它写法, 必须真在本章出现过"],
      "category": "分类",
      "definition_para": 7,
      "refinement_paras": [12, 19]
    }}
  ]
}}

## 字段说明

- **term / aliases**: 必须真的在原文中出现过 (term 或某个 alias 字面包含在你指定的段落里)
- **definition_para**: 该段落明确"定义/解释"了此概念。**段落标记 [P07] 写 7**, 不是 pid 字符串。本章无明确定义只有引用就设为 null。
- **refinement_paras**: 作者用**解释性语言**对该概念进行补充说明的段落 (如给出新的定义、对比、因果分析等)。**纯叙事性的重复出现不算 refinement** (如角色再次登场、事件中再次提到)。可空数组。
- 每个概念必须 definition_para 或 refinement_paras 至少有一项非空, 否则不要返回。

## 关键约束

1. **段落引用必须诚实**: 你写的 definition_para=7, 服务端会去 [P07] 段落里检查 term 或 alias 是否真出现; 找不到就丢弃这条引用。
2. **aliases 不能是更上位/下位概念**:
   - "向上流动"和"社会流动"是**不同**概念, 不要互列为别名 (前者是后者的子类型)
   - aliases 只放真正的同义不同写, 例如"上向流动" 是 "向上流动" 的别名
3. **抽取范围要广**: 不光抽抽象术语/理论, **人名 / 地名 / 作品名**这类专有名词, 只要在本章被作者反复提到或承担叙事作用, 也要抽出来 (它们对读者理解很重要, 释义会在后续阶段由系统结合背景补全)。
3b. **文化背景词**: 额外识别文中**作者默认读者已知、因此未做解释**的文化背景词 ({cultural_guidelines})。判断标准: 该词承载了理解上下文所必需的背景知识, 但作者没有解释它。即使读者可能听过这个名字, 只要不了解其具体含义、立场差异或社会意义就会影响理解, 就应该提取。这类词 category 标为 "cultural_context"。definition_para 设为该词首次出现的段落编号。
4. **宁少勿多**: 每 10 段 ≤ {quantity} 个高质量概念。没把握就跳过。
5. **不要返回 mention 类引用** (顺带提及由后续阶段自动补全, 你只管 definition / refinement)。
6. **不要写 initial_definition 字段**: 释义会在后续阶段单独生成, 你只管识别和定位。

## 章节文本

{paragraphs_text}

---

直接输出 JSON。"""

    return _call_llm(
        system="你是一个精确的书籍概念抽取助手。",
        prompt=prompt,
        max_tokens=4000,
        config=config,
    )["concepts"]


def _synthesize_definitions_batch(
    concepts: list[dict], strategy: dict, config: LLMConfig | None = None
) -> dict[str, str]:
    """批量为概念合成 initial_definition. 返回 {term: definition}.

    每个概念给 LLM 看: term + aliases + category + parent + evidence 句子.
    LLM 区分 "术语" 和 "专有名词" 两类写法.
    """
    if not concepts:
        return {}

    # evidence 取材: 优先 definition 角色, 不够再 refinement; 限制 3 条 / 每条 100 字
    # 太多句子会让 prompt 飙到 3-4K token, 模型容易返回空字符串.
    MAX_EV = 3
    MAX_QUOTE_CHARS = 100

    def _pick_evidence(c: dict) -> list[dict]:
        evs = c.get("evidence") or []
        defs = [e for e in evs if e.get("role") == "definition"]
        refs = [e for e in evs if e.get("role") == "refinement"]
        return (defs + refs)[:MAX_EV]

    blocks = []
    for i, c in enumerate(concepts, 1):
        ev_lines = []
        for ev in _pick_evidence(c):
            ch = ev.get("chapter_idx", "?")
            quote = (ev.get("quote") or "").strip()
            if not quote:
                continue
            if len(quote) > MAX_QUOTE_CHARS:
                quote = quote[:MAX_QUOTE_CHARS] + "…"
            ev_lines.append(f"  [第{ch}章] {quote}")
        ev_text = "\n".join(ev_lines) if ev_lines else "  (无)"

        parent_line = (
            f"  父概念: {c['_parent_term']}\n" if c.get("_parent_term") else ""
        )
        aliases = c.get("aliases") or []
        aliases_line = f"  别名: {aliases}\n" if aliases else ""

        blocks.append(
            f"[{i}] term: {c['term']}\n"
            f"  分类: {c.get('category', 'term')}\n"
            f"{parent_line}"
            f"{aliases_line}"
            f"  原文句子:\n{ev_text}"
        )

    prompt = f"""你是读书 app 的概念释义生成器, 要为读者写鼠标悬停时看的解释.

## 书籍背景

类型: {strategy.get('book_type', '未知')}
概述: {strategy.get('book_summary', '')}

## 任务

为下面 {len(concepts)} 个概念各生成 1 句释义 (≤100 字).

## 释义原则

- **抽象术语 / 理论 / 主题**: 综合 evidence 句子提炼"它是什么", 不要照抄原句.
- **专有名词 (人名 / 地名 / 作品名)**: evidence 句子里通常没有定义, 你要**结合书籍背景 + 你自己的常识**告诉读者:
  - 人名: 是谁, 与作者/书的关系或在书中扮演的角色
  - 地名: 在哪, 有何相关背景 (历史/地理/经济)
  - 作品名: 谁写的, 关于什么
- 有 **父概念** 时, 释义要点出与父概念的差异 (例如父概念是"社会流动"时, "向上流动"要强调"向上"的方向性).
- **文化背景词 (category=cultural_context)**: 解释该词的文化背景, 包括它是什么、在其所属文化中意味什么、为什么对理解上下文很重要. 不要求使用作者原话.
- **释义要独立可读**, 不要写"作者用此词指代…"这种依赖上下文的话.
- 若信息实在不足, 就用 evidence 句子里能看出的最小线索写一句中性描述, 不要乱编.

## 概念列表

{chr(10).join(blocks)}

## 输出 (严格 JSON, terms 顺序与上面一致)

{{
  "definitions": [
    {{"term": "概念term原样", "definition": "释义"}}
  ]
}}

直接输出 JSON。"""

    result = _call_llm(
        system="你是一个读书 app 的概念释义生成器, 输出简洁、独立可读的释义。",
        prompt=prompt,
        max_tokens=2000,
        config=config,
    )

    out: dict[str, str] = {}
    for entry in result.get("definitions") or []:
        term = (entry.get("term") or "").strip()
        defn = (entry.get("definition") or "").strip()
        if term and defn:
            out[term] = defn
    return out


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?\.])")


def _build_evidence_from_para(
    para: dict, term: str, aliases: list[str], role: str
) -> dict | None:
    """在段落里找 term 或某个 alias 的位置, 取所在句作为 quote.

    返回 evidence dict; 段落里根本没有 term/alias 则 None.
    优先 term, 其次按长度降序的 alias.
    """
    text = para["text"]
    text_lower = text.lower()
    candidates = [term] + sorted([a for a in aliases if a], key=len, reverse=True)

    hit_pos = -1
    for kw in candidates:
        if not kw:
            continue
        pos = text_lower.find(kw.lower())
        if pos >= 0:
            hit_pos = pos
            break
    if hit_pos < 0:
        return None

    sentences = _SENTENCE_SPLIT_RE.split(text)
    cursor = 0
    quote, quote_offset = None, 0
    for s in sentences:
        s_len = len(s)
        if cursor <= hit_pos < cursor + s_len:
            stripped = s.strip()
            if stripped:
                quote = stripped
                quote_offset = cursor + (s_len - len(s.lstrip()))
            break
        cursor += s_len
    if not quote:
        # 句切失败兜底: hit 周围 ±60 字符
        start = max(0, hit_pos - 30)
        end = min(len(text), hit_pos + 80)
        chunk = text[start:end]
        quote = chunk.strip()
        quote_offset = start + (len(chunk) - len(chunk.lstrip()))

    return {
        "pid": para["pid"],
        "quote": quote,
        "role": role,
        "char_offset": quote_offset,
        "char_length": len(quote),
    }


def _validate_evidence(concepts: list[dict], paragraphs: list[dict]) -> list[dict]:
    """把 LLM 给的 (definition_para, refinement_paras) 翻译成 evidence rows.

    LLM 只承诺“哪些段落讨论这个概念”, 服务端从段落里抓含 term/alias 的句子
    作为 quote. 校验只确认: 段落里真有 term 或 alias 出现, 否则丢这条引用.

    兼容旧字段 evidence: [{para, role}] (quote 字段忽略, 服务端重新抽).
    """
    para_by_idx = {p["para_idx"]: p for p in paragraphs}

    def _coerce_para(ref):
        if isinstance(ref, int):
            return para_by_idx.get(ref)
        if isinstance(ref, str) and ref.strip().lstrip("Pp").isdigit():
            return para_by_idx.get(int(ref.strip().lstrip("Pp")))
        return None

    dropped_para_refs = 0
    cleaned = []
    for c in concepts:
        term = (c.get("term") or "").strip()
        if not term:
            continue
        aliases = [a.strip() for a in (c.get("aliases") or []) if a and a.strip()]

        valid_evidence: list[dict] = []
        seen_keys: set[tuple[str, int]] = set()

        def _try_add(para_ref, role):
            nonlocal dropped_para_refs
            para = _coerce_para(para_ref)
            if para is None:
                return
            ev = _build_evidence_from_para(para, term, aliases, role)
            if ev is None:
                dropped_para_refs += 1
                return
            key = (ev["pid"], ev["char_offset"])
            if key in seen_keys:
                return
            seen_keys.add(key)
            valid_evidence.append(ev)

        # 新格式
        _try_add(c.get("definition_para"), "definition")
        for r in c.get("refinement_paras") or []:
            _try_add(r, "refinement")
        # 旧格式兼容
        for ev_in in c.get("evidence") or []:
            role_in = ev_in.get("role")
            if role_in not in ("definition", "refinement"):
                continue
            _try_add(ev_in.get("para") or ev_in.get("pid"), role_in)

        if not valid_evidence:
            continue

        # initial_definition 占位空字符串, Phase 2.5 会基于 evidence 句子合成释义.
        cleaned.append({
            "term": term,
            "aliases": aliases,
            "category": c.get("category", "term"),
            "initial_definition": "",
            "evidence": valid_evidence,
        })

    if dropped_para_refs:
        logger.info(
            f"[validate] dropped {dropped_para_refs} para refs "
            f"(指定段落里没有 term/alias)"
        )
    return cleaned


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
            existing.setdefault("source_chapters", [])
            if c.get("source_chapter_idx") not in existing["source_chapters"]:
                existing["source_chapters"].append(c["source_chapter_idx"])
            # Evidence 合并: 跨章去重 (按 pid+char_offset 唯一)
            existing.setdefault("evidence", [])
            seen_keys = {(e["pid"], e["char_offset"]) for e in existing["evidence"]}
            for ev in c.get("evidence", []):
                key = (ev["pid"], ev["char_offset"])
                if key not in seen_keys:
                    existing["evidence"].append(ev)
                    seen_keys.add(key)
        else:
            entry = {
                "term": term,
                "aliases": c.get("aliases", []),
                "category": c.get("category", "term"),
                "initial_definition": c.get("initial_definition", ""),
                "source_chapter_idx": c.get("source_chapter_idx"),
                "source_chapter_title": c.get("source_chapter_title"),
                "source_chapters": [c.get("source_chapter_idx")],
                "evidence": list(c.get("evidence", [])),
            }
            merged[term_lower] = entry
            for alias in c.get("aliases", []):
                alias_map[alias.strip().lower()] = term_lower

    return list(merged.values())


def _llm_concept_linker(
    concepts: list[dict],
    sim_threshold: float = 0.75,
    top_k: int = 3,
    batch_size: int = 10,
    config: LLMConfig | None = None,
    emb_config: dict | None = None,
) -> list[dict]:
    """Embedding 产候选 + LLM 拍板.

    旧 _embedding_merge 用 cosine ≥ 0.85 直接合并, 会把"社会流动"<->"向上流动"
    这种相关但不同的概念错合成同义. 这里 LLM 对每对候选明确给出三种判定:
      - SAME: 同一概念不同写法 -> 合并
      - PARENT_CHILD: 上下位关系 -> 不合并, 设置 child._parent_term
      - UNRELATED: 不动

    Args:
      concepts: list of {term, aliases, evidence, ...}
      sim_threshold: embedding 余弦下限, 不达标就连 LLM 都不送
      top_k: 每个概念最多和多少个高相似度邻居配对
    """
    n = len(concepts)
    if n <= 1:
        return concepts

    terms = [c["term"] for c in concepts]
    embeddings = _get_embeddings(terms, emb_config)
    if not embeddings or len(embeddings) != n:
        logger.warning("Embedding API failed, skip LLM linker (no merge / no parent)")
        return concepts

    # 1. 候选对生成: 每个 i 找 top_k 个 j (j>i 避免对称)
    candidate_pairs: list[tuple[int, int, float]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for i in range(n):
        sims = [
            (j, _cosine_similarity(embeddings[i], embeddings[j]))
            for j in range(n) if j != i
        ]
        sims = [s for s in sims if s[1] >= sim_threshold]
        sims.sort(key=lambda x: x[1], reverse=True)
        for j, sim in sims[:top_k]:
            key = (min(i, j), max(i, j))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            candidate_pairs.append((key[0], key[1], sim))

    if not candidate_pairs:
        return concepts

    logger.info(f"LLM linker: {len(candidate_pairs)} candidate pairs from {n} concepts")

    # 2. 分批送 LLM
    verdicts: dict[tuple[int, int], dict] = {}
    for chunk_start in range(0, len(candidate_pairs), batch_size):
        chunk = candidate_pairs[chunk_start:chunk_start + batch_size]
        batch_verdicts = _judge_concept_pairs(concepts, chunk, config)
        verdicts.update(batch_verdicts)

    # 3. 处理 SAME (合并) — 用 union-find 处理传递
    parent_uf = list(range(n))

    def find(x):
        while parent_uf[x] != x:
            parent_uf[x] = parent_uf[parent_uf[x]]
            x = parent_uf[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            # 索引小的当 root, 保证稳定
            parent_uf[max(ra, rb)] = min(ra, rb)

    parent_child: dict[int, int] = {}
    same_count = 0
    pc_count = 0
    for (i, j), v in verdicts.items():
        verdict = v.get("verdict")
        if verdict == "SAME":
            union(i, j)
            same_count += 1
            logger.debug(
                f"LLM linker SAME: '{concepts[i]['term']}' <-> '{concepts[j]['term']}'"
            )
        elif verdict == "PARENT_CHILD":
            parent_label = v.get("parent")
            if parent_label not in ("A", "B"):
                continue
            parent_idx = i if parent_label == "A" else j
            child_idx = j if parent_label == "A" else i
            parent_child[child_idx] = parent_idx
            pc_count += 1
            logger.debug(
                f"LLM linker PARENT_CHILD: "
                f"parent='{concepts[parent_idx]['term']}' "
                f"child='{concepts[child_idx]['term']}'"
            )
    if same_count or pc_count:
        logger.info(f"LLM linker: SAME={same_count}, PARENT_CHILD={pc_count}, others=UNRELATED")

    # 4. 应用 SAME 合并: 每个组挑一个代表 (root)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    result: list[dict] = []
    idx_to_term: dict[int, str] = {}  # 旧 idx -> 合并后代表 term
    for root, members in groups.items():
        rep = concepts[root].copy()
        # 合并 aliases / source_chapters / evidence
        merged_aliases = set(rep.get("aliases", []))
        merged_chapters = list(rep.get("source_chapters", []))
        merged_evidence = list(rep.get("evidence", []))
        seen_ev_keys = {(e["pid"], e["char_offset"]) for e in merged_evidence}

        for m in members:
            if m == root:
                continue
            other = concepts[m]
            merged_aliases.add(other["term"])
            merged_aliases.update(other.get("aliases", []))
            for ch in other.get("source_chapters", []):
                if ch not in merged_chapters:
                    merged_chapters.append(ch)
            for ev in other.get("evidence", []):
                key = (ev["pid"], ev["char_offset"])
                if key not in seen_ev_keys:
                    merged_evidence.append(ev)
                    seen_ev_keys.add(key)
        merged_aliases.discard(rep["term"])
        rep["aliases"] = list(merged_aliases)
        rep["source_chapters"] = merged_chapters
        rep["evidence"] = merged_evidence
        # initial_definition: 优先现有的, 没有就用 evidence 里第一条 definition 的 quote
        if not rep.get("initial_definition"):
            first_def = next(
                (e for e in merged_evidence if e["role"] == "definition"),
                None,
            )
            if first_def:
                rep["initial_definition"] = first_def["quote"]

        for m in members:
            idx_to_term[m] = rep["term"]
        result.append(rep)

    # 5. 应用 PARENT_CHILD: 用代表 term 标记 _parent_term, 持久化时再解析为 id
    rep_term_to_obj = {c["term"]: c for c in result}
    for child_idx, parent_idx in parent_child.items():
        child_rep_term = idx_to_term.get(child_idx)
        parent_rep_term = idx_to_term.get(parent_idx)
        if not child_rep_term or not parent_rep_term:
            continue
        if child_rep_term == parent_rep_term:
            # 已经被 SAME 合到一起了, 不再设 parent
            continue
        child_obj = rep_term_to_obj.get(child_rep_term)
        if child_obj is not None:
            child_obj["_parent_term"] = parent_rep_term

    return result


def _judge_concept_pairs(
    concepts: list[dict],
    pairs: list[tuple[int, int, float]],
    config: LLMConfig | None = None,
) -> dict[tuple[int, int], dict]:
    """送 LLM 判定一批候选对的关系."""
    if not pairs:
        return {}

    def _short_def(c: dict) -> str:
        d = c.get("initial_definition") or ""
        return (d[:80] + "…") if len(d) > 80 else d

    pair_block = []
    for k, (i, j, sim) in enumerate(pairs, 1):
        ca, cb = concepts[i], concepts[j]
        pair_block.append(
            f'[{k}] sim={sim:.2f}\n'
            f'  A: term="{ca["term"]}" aliases={ca.get("aliases", [])} 定义="{_short_def(ca)}"\n'
            f'  B: term="{cb["term"]}" aliases={cb.get("aliases", [])} 定义="{_short_def(cb)}"'
        )
    pair_text = "\n".join(pair_block)

    prompt = f"""你是概念关系判定器。下面有若干对候选概念对, 每对的 A/B 都带其定义。

判定规则:
- SAME: 字面不同但所指完全相同 (例: "上向流动" 与 "向上流动")
- PARENT_CHILD: 一个是另一个的真子集 / 实例化 (例: "社会流动" 包含 "向上流动", "向下流动" 是 "社会流动" 的子类)。需指出 parent 是 A 还是 B。
- UNRELATED: 不是同概念也不是父子关系, 即使主题相邻也判 UNRELATED。

判定时优先看 **定义**, 不要光看名字相似度。

候选对:
{pair_text}

输出严格 JSON, 数组顺序与候选对编号一致:

{{
  "judgments": [
    {{"pair": 1, "verdict": "SAME"}},
    {{"pair": 2, "verdict": "PARENT_CHILD", "parent": "A"}},
    {{"pair": 3, "verdict": "UNRELATED"}}
  ]
}}

直接输出 JSON。"""

    try:
        result = _call_llm(
            system="你是一个严谨的概念关系判定器。",
            prompt=prompt,
            max_tokens=2000,
            config=config,
        )
        out: dict[tuple[int, int], dict] = {}
        for j in result.get("judgments", []):
            pair_num = j.get("pair")
            if not isinstance(pair_num, int) or not (1 <= pair_num <= len(pairs)):
                continue
            i, jj, _ = pairs[pair_num - 1]
            out[(i, jj)] = j
        return out
    except Exception as e:
        logger.warning(f"LLM linker judgment failed, fallback to UNRELATED for batch: {e}")
        return {}


def _get_embeddings(texts: list[str], emb_config: dict | None = None) -> list[list[float]] | None:
    api_key = (emb_config or {}).get("api_key") or CONCEPT_EMBED_API_KEY
    base_url = (emb_config or {}).get("base_url") or CONCEPT_EMBED_BASE_URL
    model = (emb_config or {}).get("model") or CONCEPT_EMBED_MODEL
    if not api_key:
        return None
    try:
        resp = httpx.post(
            base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # API 返回的 data 按 index 排序
        data.sort(key=lambda x: x["index"])
        return [item["embedding"] for item in data]
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
