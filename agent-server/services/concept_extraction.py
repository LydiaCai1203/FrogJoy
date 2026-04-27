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

import anthropic
import httpx
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import (
    IndexedBook, IndexedParagraph, Concept, ConceptOccurrence, ConceptEvidence,
)


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
                raw = _call_phase1_llm(toc, chapter, paragraphs, strategy)
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
        if EMBEDDING_API_KEY:
            person_categories = {"person", "character"}
            non_person = [c for c in merged if c.get("category") not in person_categories]
            persons = [c for c in merged if c.get("category") in person_categories]
            non_person = _llm_concept_linker(non_person, sim_threshold=0.75, top_k=3)
            merged = non_person + persons

        return merged

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
    }


def _call_llm(system, prompt, max_tokens=4000, max_retries=3):
    client = anthropic.Anthropic(
        api_key=MINIMAX_LLM_API_KEY,
        base_url=MINIMAX_LLM_BASE_URL,
    )
    last_error = None
    for attempt in range(max_retries):
        try:
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
        except (httpx.HTTPError, anthropic.APIConnectionError, anthropic.RateLimitError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 2s, 4s
                logger.warning(f"LLM call failed (attempt {attempt+1}/{max_retries}), retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                logger.error(f"LLM call failed after {max_retries} attempts: {e}")
    raise last_error


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
      "term": "规范名 (作者原文中最常用的形式)",
      "aliases": ["原文中实际出现的其它写法"],
      "category": "分类",
      "evidence": [
        {{
          "pid": "段落标记里 [P##|pid] 的 pid 部分",
          "quote": "从该段落中原文逐字抄录的片段, 必须包含 term 或某个 alias",
          "role": "definition 或 refinement"
        }}
      ]
    }}
  ]
}}

## 关键约束 (违反会被服务端剔除)

1. **quote 必须逐字**: 原文中能 Ctrl+F 搜到, 标点空格一字不差。不可改写, 不可摘要。
2. **quote 必须包含 term 或某个 alias**: 这是该 evidence 锚定到此概念的依据。
3. **quote 必须真的在 pid 指向的段落里**: 不要凭印象写 pid。
4. **role 二选一**:
   - definition: 作者明确给出该概念的定义、解释、含义
   - refinement: 作者补充、深化、举例、引申该概念
   不要写 mention (顺带提及由后续阶段补全)。
5. **每个概念至少 1 条 evidence, 没有就别返回这个概念**。
6. **aliases 不能是更上位/下位概念**: 如"向上流动"和"社会流动"是不同概念, 不要互列为别名。aliases 只放真正的同义写法 (如"上向流动" 是 "向上流动" 的别名)。

## 数量

- 宁少勿多, 每 10 段 ≤ {quantity} 个高质量概念
- 没把握就跳过, 不要凑数

## 章节文本

{paragraphs_text}

---

直接输出 JSON。"""

    return _call_llm(
        system="你是一个精确的书籍概念抽取助手。",
        prompt=prompt,
        max_tokens=4000,
    )["concepts"]


def _validate_evidence(concepts: list[dict], paragraphs: list[dict]) -> list[dict]:
    """服务端校验 LLM 返回的 evidence, 剔除虚构内容.

    规则:
      - quote 必须逐字出现在 evidence.pid 指向的段落
      - quote 必须包含 term 或某个 alias (大小写不敏感)
      - role 必须是 definition 或 refinement
      - 校验完仍有 ≥1 条 evidence 的概念才保留
    """
    para_by_pid = {p["pid"]: p["text"] for p in paragraphs}

    cleaned = []
    for c in concepts:
        term = (c.get("term") or "").strip()
        if not term:
            continue
        aliases = [a.strip() for a in (c.get("aliases") or []) if a and a.strip()]
        keywords_lower = {term.lower(), *(a.lower() for a in aliases)}

        valid_evidence = []
        for ev in c.get("evidence") or []:
            pid = ev.get("pid")
            quote = (ev.get("quote") or "").strip()
            role = ev.get("role")

            if role not in ("definition", "refinement"):
                continue
            if not pid or not quote:
                continue
            para_text = para_by_pid.get(pid)
            if para_text is None:
                logger.debug(f"Evidence pid={pid} not in current chapter, drop")
                continue
            char_offset = para_text.find(quote)
            if char_offset < 0:
                logger.debug(
                    f"Evidence quote not literally in paragraph "
                    f"(term='{term}', pid={pid}, quote={quote[:30]!r}...)"
                )
                continue
            quote_lower = quote.lower()
            if not any(kw in quote_lower for kw in keywords_lower):
                logger.debug(
                    f"Evidence quote does not contain term/alias "
                    f"(term='{term}', quote={quote[:30]!r}...)"
                )
                continue
            valid_evidence.append({
                "pid": pid,
                "quote": quote,
                "role": role,
                "char_offset": char_offset,
                "char_length": len(quote),
            })

        if not valid_evidence:
            logger.debug(f"Concept '{term}' dropped: no valid evidence")
            continue

        # initial_definition: 取首条 definition 类 evidence; 没有则用首条 refinement
        first_def = next(
            (e for e in valid_evidence if e["role"] == "definition"),
            None,
        )
        first_any = first_def or valid_evidence[0]

        cleaned.append({
            "term": term,
            "aliases": aliases,
            "category": c.get("category", "term"),
            "initial_definition": first_any["quote"],
            "evidence": valid_evidence,
        })

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
    batch_size: int = 30,
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
    embeddings = _get_embeddings(terms)
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
        batch_verdicts = _judge_concept_pairs(concepts, chunk)
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

    parent_child: dict[int, int] = {}  # child_idx -> parent_idx (unmerged)
    for (i, j), v in verdicts.items():
        verdict = v.get("verdict")
        if verdict == "SAME":
            union(i, j)
            logger.info(
                f"LLM linker SAME: '{concepts[i]['term']}' <-> '{concepts[j]['term']}'"
            )
        elif verdict == "PARENT_CHILD":
            # parent / child 字段是 "A" 或 "B" 字面
            parent_label = v.get("parent")
            if parent_label not in ("A", "B"):
                continue
            parent_idx = i if parent_label == "A" else j
            child_idx = j if parent_label == "A" else i
            parent_child[child_idx] = parent_idx
            logger.info(
                f"LLM linker PARENT_CHILD: "
                f"parent='{concepts[parent_idx]['term']}' "
                f"child='{concepts[child_idx]['term']}'"
            )

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


def _get_embeddings(texts: list[str]) -> list[list[float]] | None:
    if not EMBEDDING_API_KEY:
        return None
    try:
        resp = httpx.post(
            EMBEDDING_BASE_URL,
            headers={
                "Authorization": f"Bearer {EMBEDDING_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": EMBEDDING_MODEL, "input": texts},
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
