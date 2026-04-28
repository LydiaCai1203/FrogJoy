"""
概念提取 Service — A2A Client 模式

查询方法 (get_concepts, get_chapter_annotations 等) 仍在 backend 本地执行。
提取任务 (build_concepts, cancel_extraction) 通过 A2A 协议委托给 agent-server。

任务状态走 tasks 表 (DB 持久化), 重启不丢; 进度由 get_status 从 A2A
拉取最新值, 同步到 tasks 表.
"""
from __future__ import annotations

import json
import uuid

import httpx
from loguru import logger
from sqlalchemy.exc import IntegrityError

from shared.config import settings
from shared.database import get_db
from shared.models import (
    IndexedBook, IndexedParagraph, Concept, ConceptOccurrence, ConceptEvidence,
)
from app.services.index_service import IndexService
from app.services import tasks


TASK_TYPE = "concept_extraction"


class ConceptService:

    # ===================================================================
    # Build (A2A Client)
    # ===================================================================

    @classmethod
    def build_concepts(cls, book_id: str, user_id: str, rebuild: bool = False) -> str | None:
        """通过 A2A 协议委托 agent-server 抽概念. 返回 backend task id."""
        status = IndexService.get_status(book_id, user_id)
        if not status or status["status"] != "parsed":
            raise ValueError("Index not ready, build index first")

        # 防重复点击: 查 tasks 表是否已有同书运行中任务
        running = tasks.find_running(user_id, TASK_TYPE, book_id)
        if running:
            return running["id"]

        # 已 enriched 且非 rebuild, 不再抽
        with get_db() as db:
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()
            if record and not rebuild and record.concept_status == "enriched":
                return None

        # 1. 先建 Task 行 (running 状态), 占位
        # 部分唯一索引 uq_tasks_running 兜底并发竞争: find_running 漏过的
        # race 在这里会撞 IntegrityError, 改读已存在的那条
        try:
            tid = tasks.create(
                user_id=user_id,
                task_type=TASK_TYPE,
                book_id=book_id,
                message="任务已提交",
            )
        except IntegrityError:
            logger.info(
                f"Race detected on concept extraction kickoff "
                f"(user={user_id} book={book_id}); reusing existing task"
            )
            existing = tasks.find_running(user_id, TASK_TYPE, book_id)
            return existing["id"] if existing else None

        # 2. 同步 IndexedBook.concept_status (UI 现有读路径仍依赖)
        cls._set_status(book_id, user_id, "extracting")

        # 3. POST agent-server kickoff
        payload = json.dumps({
            "book_id": book_id,
            "user_id": user_id,
            "rebuild": rebuild,
        })
        try:
            agent_url = settings.agent_server_url
            resp = httpx.post(
                f"{agent_url}/default/message:send",
                headers={"A2A-Version": "1.0"},
                json={
                    "message": {
                        "messageId": str(uuid.uuid4()),
                        "role": "ROLE_USER",
                        "parts": [{"text": payload}],
                    },
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            task_data = data.get("task", {})
            a2a_task_id = task_data.get("id", "")
            logger.info(f"A2A task created: tid={tid} a2a={a2a_task_id}")
            tasks.set_external_id(tid, a2a_task_id)
            return tid

        except httpx.ReadTimeout:
            # kickoff 超时不一定表示 agent 没收到. 保留 task 在 running 状态,
            # 让 zombie 清理或后续 polling 兜底; 后续点击会被 find_running 挡住.
            logger.warning(f"A2A kickoff timed out (book={book_id}, tid={tid})")
            return tid
        except Exception as e:
            logger.exception(f"Failed to send A2A message: {e}")
            tasks.fail(tid, str(e))
            cls._set_status(book_id, user_id, "failed", str(e))
            raise

    @classmethod
    def is_a2a_task_alive(cls, external_id: str | None) -> bool:
        """探 agent-server 上指定 A2A task 是否还在工作.

        给 tasks.cleanup_zombies 当回调用, 避免把跑了很久但仍在干活的大书任务
        误标 failed. 拿不准就当死 (False), 让上层标 failed 是更安全的默认.
        """
        if not external_id:
            return False
        try:
            agent_url = settings.agent_server_url
            resp = httpx.get(
                f"{agent_url}/default/tasks/{external_id}",
                headers={"A2A-Version": "1.0"},
                timeout=3,
            )
            if resp.status_code != 200:
                return False
            state = resp.json().get("status", {}).get("state", "")
            return state in ("TASK_STATE_WORKING", "TASK_STATE_SUBMITTED")
        except Exception:
            return False

    @classmethod
    def cancel_extraction(cls, book_id: str, user_id: str) -> bool:
        """取消该书正在进行的概念提取."""
        running = tasks.find_running(user_id, TASK_TYPE, book_id)
        if not running:
            return False

        a2a_task_id = running.get("external_id")
        if a2a_task_id:
            try:
                agent_url = settings.agent_server_url
                resp = httpx.post(
                    f"{agent_url}/default/tasks/{a2a_task_id}:cancel",
                    headers={"A2A-Version": "1.0"},
                    timeout=10,
                )
                resp.raise_for_status()
                logger.info(f"A2A cancel sent: a2a={a2a_task_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel A2A task: {e}")
                # 即使 A2A 取消失败也把 DB 标 cancelled, 防僵尸

        tasks.cancel(running["id"])
        cls._set_status(book_id, user_id, None, "用户取消")
        return True

    # ===================================================================
    # Status (混合: DB + A2A 任务进度)
    # ===================================================================

    @classmethod
    def get_status(cls, book_id, user_id) -> dict | None:
        """组合返回:
          - concept_status: 来自 IndexedBook (是否已 enriched 等)
          - progress / progress_text: 来自 tasks 表 + 实时 A2A 拉取
        """
        with get_db() as db:
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()
            if not record:
                return None

        # 找当前活跃任务, 同步进度
        running = tasks.find_running(user_id, TASK_TYPE, book_id)
        progress = None
        progress_text = None
        if running:
            cls._sync_task_from_a2a(running)
            # 重读 (sync 可能转成终态)
            running = tasks.get(running["id"])
            if running and running["status"] == "running":
                progress = running.get("progress")
                progress_text = running.get("message")

        # IndexedBook 状态可能在 sync 时被改, 重读
        with get_db() as db:
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()
            if not record:
                return None

            # 自愈: IndexedBook 说 extracting 但实际无 running 任务时
            # (典型场景: zombie cleanup 把 task 标 failed 但 IndexedBook
            # 没同步; 或 task 在 sync 步骤刚转成终态)
            # → 按最近一次任务的终态修正 IndexedBook
            if record.concept_status == "extracting" and not running:
                latest = tasks.find_latest(user_id, TASK_TYPE, book_id)
                if latest and latest["status"] == "completed":
                    record.concept_status = "enriched"
                    record.concept_error = None
                elif latest and latest["status"] in ("failed", "cancelled"):
                    record.concept_status = None
                    record.concept_error = latest.get("message")
                else:
                    # 没任何任务记录, 数据不一致, 重置让用户能重试
                    record.concept_status = None
                    record.concept_error = None
                db.commit()

            return {
                "concept_status": record.concept_status,
                "concept_error": record.concept_error,
                "total_concepts": record.total_concepts,
                "progress": progress,
                "progress_text": progress_text,
            }

    @classmethod
    def _sync_task_from_a2a(cls, task: dict) -> None:
        """从 agent-server 拉 A2A task 最新状态, 同步到 tasks 表和 IndexedBook."""
        a2a_task_id = task.get("external_id")
        if not a2a_task_id:
            return

        try:
            agent_url = settings.agent_server_url
            resp = httpx.get(
                f"{agent_url}/default/tasks/{a2a_task_id}",
                headers={"A2A-Version": "1.0"},
                timeout=5,
            )
            if resp.status_code != 200:
                return

            data = resp.json()
            status = data.get("status", {})
            state = status.get("state", "")

            msg = status.get("message", {})
            parts = msg.get("parts", [])
            text = ""
            progress_val = None
            for p in parts:
                if p.get("text"):
                    text = p["text"]
            msg_meta = msg.get("metadata", {})
            if isinstance(msg_meta, dict) and "progress" in msg_meta:
                progress_val = msg_meta["progress"]

            tid = task["id"]
            book_id = task["book_id"]
            user_id = task["user_id"]

            if state == "TASK_STATE_COMPLETED":
                # text 是 agent 返回的 result JSON
                summary = text or "完成"
                tasks.complete(tid, summary)
                cls._set_status(book_id, user_id, "enriched")
                try:
                    result = json.loads(text)
                    with get_db() as db:
                        rec = db.query(IndexedBook).filter_by(
                            book_id=book_id, user_id=user_id
                        ).first()
                        if rec:
                            rec.total_concepts = result.get("concepts", 0)
                            db.commit()
                except (json.JSONDecodeError, TypeError):
                    pass
            elif state == "TASK_STATE_FAILED":
                tasks.fail(tid, text or "提取失败")
                cls._set_status(book_id, user_id, "failed", text)
            elif state == "TASK_STATE_CANCELED":
                tasks.cancel(tid, text or "用户取消")
                cls._set_status(book_id, user_id, None, "用户取消")
            else:
                if progress_val is not None or text:
                    tasks.update_progress(tid, progress_val or 0, text or None)

        except Exception as e:
            logger.debug(f"Failed to sync A2A task {a2a_task_id}: {e}")

    # ===================================================================
    # 查询 (本地 DB, 不变)
    # ===================================================================

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
        """返回某章的概念角标数据 (前端渲染用)。

        合并两表: ConceptEvidence (definition/refinement, LLM grounded)
                + ConceptOccurrence (mention, Phase 3 regex 补全)。
        前者带 quote 作 core_sentence; 二者都给 matched_text 让前端定位。
        evidence 的 matched_text 是 quote 中真实出现的 term 或 alias 字串
        (优先 term, 其次最长 alias), 避免引文整段不好命中句子的问题。
        """
        with get_db() as db:
            chapter_evs = (
                db.query(ConceptEvidence)
                .filter_by(
                    book_id=book_id, user_id=user_id, chapter_idx=chapter_idx
                )
                .all()
            )
            chapter_occs = (
                db.query(ConceptOccurrence)
                .filter_by(
                    book_id=book_id, user_id=user_id, chapter_idx=chapter_idx
                )
                .all()
            )
            if not chapter_evs and not chapter_occs:
                return []

            # 批量取段落 idx
            paragraph_ids = (
                {ev.paragraph_id for ev in chapter_evs}
                | {o.paragraph_id for o in chapter_occs}
            )
            para_idx_by_id: dict[str, int] = {}
            if paragraph_ids:
                paras = (
                    db.query(IndexedParagraph)
                    .filter(IndexedParagraph.id.in_(paragraph_ids))
                    .all()
                )
                para_idx_by_id = {p.id: p.para_idx_in_chapter for p in paras}

            # 批量取相关概念 + 它们的 parent (parent 可能不在本章 occs 里)
            concept_ids = (
                {ev.concept_id for ev in chapter_evs}
                | {o.concept_id for o in chapter_occs}
            )
            if not concept_ids:
                return []
            concepts = (
                db.query(Concept)
                .filter(Concept.id.in_(concept_ids))
                .all()
            )
            concepts_by_id = {c.id: c for c in concepts}

            parent_ids = {
                c.parent_concept_id for c in concepts
                if c.parent_concept_id and c.parent_concept_id not in concepts_by_id
            }
            parent_terms_by_id: dict[str, str] = {}
            if parent_ids:
                parent_rows = db.query(Concept).filter(Concept.id.in_(parent_ids)).all()
                parent_terms_by_id = {p.id: p.term for p in parent_rows}
            for c in concepts:
                if c.id not in parent_terms_by_id and c.id in concepts_by_id:
                    parent_terms_by_id[c.id] = c.term

            def _resolve_parent_term(c: Concept) -> str | None:
                if not c.parent_concept_id:
                    return None
                if c.parent_concept_id in parent_terms_by_id:
                    return parent_terms_by_id[c.parent_concept_id]
                # parent 也在 concepts_by_id 里
                pc = concepts_by_id.get(c.parent_concept_id)
                return pc.term if pc else None

            def _pick_matched_text(quote: str, c: Concept) -> str:
                aliases = c.aliases if isinstance(c.aliases, list) else (
                    json.loads(c.aliases) if c.aliases else []
                )
                # 优先 term, 其次按长度降序的 alias
                if c.term and c.term in quote:
                    return c.term
                for kw in sorted([a for a in aliases if a], key=len, reverse=True):
                    if kw in quote:
                        return kw
                return c.term or ""

            # 把 evidence 和 occurrence 都规范成同一个结构, 按概念聚合
            occ_records: dict[str, list[dict]] = {}

            for ev in chapter_evs:
                c = concepts_by_id.get(ev.concept_id)
                if not c:
                    continue
                occ_records.setdefault(ev.concept_id, []).append({
                    "para_idx_in_chapter": para_idx_by_id.get(ev.paragraph_id, -1),
                    "occurrence_type": ev.role,            # definition / refinement
                    "matched_text": _pick_matched_text(ev.quote, c),
                    "core_sentence": ev.quote,
                })

            for o in chapter_occs:
                c = concepts_by_id.get(o.concept_id)
                if not c:
                    continue
                occ_records.setdefault(o.concept_id, []).append({
                    "para_idx_in_chapter": para_idx_by_id.get(o.paragraph_id, -1),
                    "occurrence_type": "mention",
                    "matched_text": o.matched_text,
                    "core_sentence": None,
                })

            if not occ_records:
                return []

            def first_para_idx(cid: str) -> int:
                return min(r["para_idx_in_chapter"] for r in occ_records[cid])

            sorted_cids = sorted(occ_records.keys(), key=first_para_idx)

            annotations: list[dict] = []
            for badge_num, cid in enumerate(sorted_cids, 1):
                c = concepts_by_id[cid]
                records_sorted = sorted(
                    occ_records[cid], key=lambda r: r["para_idx_in_chapter"]
                )
                annotations.append({
                    "concept_id": c.id,
                    "term": c.term,
                    "category": c.category,
                    "badge_number": badge_num,
                    "popover": {
                        "term": c.term,
                        "initial_definition": c.initial_definition,
                        "total_occurrences": c.total_occurrences,
                        "parent_term": _resolve_parent_term(c),
                    },
                    "occurrences": records_sorted,
                })

            return annotations

    @classmethod
    def delete_concepts(cls, book_id, user_id) -> bool:
        with get_db() as db:
            db.query(ConceptEvidence).filter_by(
                book_id=book_id, user_id=user_id
            ).delete()
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
    # 内部工具
    # ===================================================================

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
