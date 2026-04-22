"""
概念提取 Service — A2A Client 模式

查询方法 (get_concepts, get_chapter_annotations 等) 仍在 backend 本地执行。
提取任务 (build_concepts, cancel_extraction) 通过 A2A 协议委托给 agent-server。

进度信息存在 _task_progress 内存缓存中, 由轮询/SSE 更新。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
from loguru import logger

from shared.config import settings
from shared.database import get_db
from shared.models import IndexedBook, IndexedParagraph, Concept, ConceptOccurrence
from app.services.index_service import IndexService


# A2A task 进度缓存: book_key → {task_id, progress, progress_text, state}
_task_progress: dict[str, dict] = {}


def _book_key(book_id: str, user_id: str) -> str:
    return f"{user_id}:{book_id}"


class ConceptService:

    # ===================================================================
    # Build (A2A Client)
    # ===================================================================

    @classmethod
    def build_concepts(cls, book_id: str, user_id: str, rebuild: bool = False) -> str | None:
        """
        通过 A2A 协议向 agent-server 发起概念提取。
        返回 task_id, 前端轮询 get_status 获取进度。
        """
        status = IndexService.get_status(book_id, user_id)
        if not status or status["status"] != "parsed":
            raise ValueError("Index not ready, build index first")

        if not rebuild:
            with get_db() as db:
                record = db.query(IndexedBook).filter_by(
                    book_id=book_id, user_id=user_id
                ).first()
                if record and record.concept_status == "enriched":
                    return None

        # 标记 extracting 状态
        cls._set_status(book_id, user_id, "extracting")

        # 发 A2A message:send
        payload = json.dumps({
            "book_id": book_id,
            "user_id": user_id,
            "rebuild": rebuild,
        })

        try:
            agent_url = settings.agent_server_url
            resp = httpx.post(
                f"{agent_url}/default/message:send",
                json={
                    "message": {
                        "role": "ROLE_USER",
                        "parts": [{"text": payload}],
                    },
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # A2A REST 返回 SendMessageResponse: {"task": {...}} 或 {"message": {...}}
            # protobuf JSON 用 camelCase
            task_data = data.get("task", {})
            task_id = task_data.get("id", "")
            context_id = task_data.get("contextId", "")
            logger.info(f"A2A task created: task_id={task_id} context_id={context_id}")

            key = _book_key(book_id, user_id)
            _task_progress[key] = {
                "task_id": task_id,
                "context_id": context_id,
                "progress": 0,
                "progress_text": "任务已提交",
                "state": "working",
            }

            return task_id

        except Exception as e:
            logger.exception(f"Failed to send A2A message: {e}")
            cls._set_status(book_id, user_id, "failed", str(e))
            raise

    @classmethod
    def cancel_extraction(cls, book_id: str, user_id: str) -> bool:
        """通过 A2A 协议取消正在进行的概念提取。"""
        key = _book_key(book_id, user_id)
        cached = _task_progress.get(key)
        if not cached or not cached.get("task_id"):
            return False

        task_id = cached["task_id"]

        try:
            agent_url = settings.agent_server_url
            resp = httpx.post(
                f"{agent_url}/default/tasks/{task_id}:cancel",
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"A2A cancel sent: task_id={task_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cancel A2A task: {e}")
            return False

    # ===================================================================
    # Status (混合: DB + A2A 任务进度)
    # ===================================================================

    @classmethod
    def get_status(cls, book_id, user_id) -> dict | None:
        with get_db() as db:
            record = db.query(IndexedBook).filter_by(
                book_id=book_id, user_id=user_id
            ).first()
            if not record:
                return None

            # 修复中断的 extracting 状态
            if record.concept_status == "extracting":
                concept_count = db.query(Concept).filter_by(
                    book_id=book_id, user_id=user_id
                ).count()
                if concept_count > 0:
                    record.concept_status = "enriched"
                    record.total_concepts = concept_count
                    record.concept_error = None
                    db.commit()
                elif record.updated_at:
                    if datetime.utcnow() - record.updated_at > timedelta(hours=2):
                        record.concept_status = None
                        record.concept_error = "extraction interrupted"
                        db.commit()

            # 如果正在提取, 查 A2A 任务进度
            progress = None
            progress_text = None
            if record.concept_status == "extracting":
                key = _book_key(book_id, user_id)
                cached = _task_progress.get(key)
                if cached:
                    # 先从 agent-server 拉最新状态, 更新缓存
                    cls._refresh_task_progress(book_id, user_id, cached)
                    # 再读缓存中的最新值
                    progress = cached.get("progress", 0)
                    progress_text = cached.get("progress_text", "")

            # _refresh 可能已经更新了 DB 状态, 重新读
            db.refresh(record)

            return {
                "concept_status": record.concept_status,
                "concept_error": record.concept_error,
                "total_concepts": record.total_concepts,
                "progress": progress,
                "progress_text": progress_text,
            }

    @classmethod
    def _refresh_task_progress(cls, book_id: str, user_id: str, cached: dict):
        """从 agent-server 拉取任务最新状态, 更新缓存和 DB。"""
        task_id = cached.get("task_id")
        if not task_id:
            return

        try:
            agent_url = settings.agent_server_url
            resp = httpx.get(
                f"{agent_url}/default/tasks/{task_id}",
                timeout=5,
            )
            if resp.status_code != 200:
                return

            task_data = resp.json()
            status = task_data.get("status", {})
            state = status.get("state", "")

            # 解析进度信息
            msg = status.get("message", {})
            parts = msg.get("parts", [])
            text = ""
            progress_val = None
            for p in parts:
                if p.get("text"):
                    text = p["text"]
            # 进度数字在 message.metadata.progress
            msg_meta = msg.get("metadata", {})
            if isinstance(msg_meta, dict) and "progress" in msg_meta:
                progress_val = msg_meta["progress"]

            key = _book_key(book_id, user_id)

            if state == "TASK_STATE_COMPLETED":
                _task_progress.pop(key, None)
                cls._set_status(book_id, user_id, "enriched")
                # 解析结果更新 total_concepts
                try:
                    result = json.loads(text)
                    with get_db() as db:
                        record = db.query(IndexedBook).filter_by(
                            book_id=book_id, user_id=user_id
                        ).first()
                        if record:
                            record.total_concepts = result.get("concepts", 0)
                            db.commit()
                except (json.JSONDecodeError, TypeError):
                    pass

            elif state == "TASK_STATE_FAILED":
                _task_progress.pop(key, None)
                cls._set_status(book_id, user_id, "failed", text)

            elif state == "TASK_STATE_CANCELED":
                _task_progress.pop(key, None)
                cls._set_status(book_id, user_id, None, "用户取消")

            else:
                # working — 更新进度缓存
                if progress_val is not None:
                    cached["progress"] = progress_val
                if text:
                    cached["progress_text"] = text

        except Exception as e:
            logger.debug(f"Failed to refresh task progress: {e}")

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
        """返回某章的概念角标数据 (前端渲染用)。"""
        with get_db() as db:
            chapter_occs = (
                db.query(ConceptOccurrence)
                .filter_by(
                    book_id=book_id, user_id=user_id, chapter_idx=chapter_idx
                )
                .all()
            )
            if not chapter_occs:
                return []

            concept_first_para = {}
            for occ in chapter_occs:
                if occ.concept_id not in concept_first_para:
                    para = db.query(IndexedParagraph).filter_by(
                        id=occ.paragraph_id
                    ).first()
                    concept_first_para[occ.concept_id] = (
                        para.para_idx_in_chapter if para else 999
                    )

            concepts_with_def = set()
            for cid in concept_first_para:
                c = db.query(Concept).filter_by(id=cid).first()
                if c and c.initial_definition:
                    concepts_with_def.add(cid)

            if not concepts_with_def:
                return []

            sorted_concepts = sorted(
                concepts_with_def,
                key=lambda cid: concept_first_para[cid]
            )

            annotations = []
            for badge_num, concept_id in enumerate(sorted_concepts, 1):
                c = db.query(Concept).filter_by(id=concept_id).first()
                if not c:
                    continue

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
