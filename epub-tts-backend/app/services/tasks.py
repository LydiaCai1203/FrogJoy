"""DB 持久化的后台任务生命周期服务.

面向新模块 (当前: concept_extraction) 提供. 老的 file-based task_service.py
仍在被 TTS / 翻译用着, 暂不动; 后续迁移过来后可删除老的.

状态机: running -> {completed, failed, cancelled}, 没有 pending
(agent-server kickoff 是同步的, 进库时已经在跑).

只管 lifecycle, 不知道任何业务. 业务模块负责调 create/update_progress/...
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from typing import Callable, Optional

from loguru import logger

from shared.database import get_db
from shared.models import Task


# ---------- 序列化 ----------

def to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "book_id": t.book_id,
        "task_type": t.task_type,
        "status": t.status,
        "progress": t.progress,
        "message": t.message,
        "external_id": t.external_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "finished_at": t.finished_at.isoformat() if t.finished_at else None,
    }


# ---------- 创建 ----------

def create(
    user_id: str,
    task_type: str,
    book_id: Optional[str] = None,
    external_id: Optional[str] = None,
    message: Optional[str] = None,
) -> str:
    """创建任务, 状态直接 running. 返回 task id."""
    tid = f"task:{uuid4()}"
    with get_db() as db:
        db.add(Task(
            id=tid,
            user_id=user_id,
            book_id=book_id,
            task_type=task_type,
            status="running",
            progress=0,
            message=message,
            external_id=external_id,
        ))
        db.commit()
    return tid


# ---------- 状态流转 ----------

def update_progress(task_id: str, progress: int, message: Optional[str] = None) -> None:
    """仅 running 时生效."""
    with get_db() as db:
        t = db.query(Task).filter_by(id=task_id).first()
        if not t or t.status != "running":
            return
        t.progress = max(0, min(100, progress))
        if message is not None:
            t.message = message
        db.commit()


def set_external_id(task_id: str, external_id: str) -> None:
    """kickoff 拿到 A2A task_id 后回填."""
    with get_db() as db:
        t = db.query(Task).filter_by(id=task_id).first()
        if t:
            t.external_id = external_id
            db.commit()


def complete(task_id: str, message: Optional[str] = None) -> None:
    _terminate(task_id, "completed", message=message, force_progress=100)


def fail(task_id: str, error: str) -> None:
    _terminate(task_id, "failed", message=error)


def cancel(task_id: str, message: str = "用户取消") -> None:
    _terminate(task_id, "cancelled", message=message)


def _terminate(
    task_id: str,
    status: str,
    message: Optional[str] = None,
    force_progress: Optional[int] = None,
) -> None:
    with get_db() as db:
        t = db.query(Task).filter_by(id=task_id).first()
        if not t or t.status != "running":
            return  # 已经是终态, 不重复写
        t.status = status
        if message is not None:
            t.message = message
        if force_progress is not None:
            t.progress = force_progress
        t.finished_at = datetime.utcnow()
        db.commit()


# ---------- 查询 ----------

def get(task_id: str) -> Optional[dict]:
    with get_db() as db:
        t = db.query(Task).filter_by(id=task_id).first()
        return to_dict(t) if t else None


def find_running(
    user_id: str, task_type: str, book_id: Optional[str] = None,
) -> Optional[dict]:
    """挡重复点击的核心查询: 这用户/这书/这类型有没有活任务."""
    with get_db() as db:
        q = db.query(Task).filter_by(
            user_id=user_id, task_type=task_type, status="running",
        )
        if book_id is not None:
            q = q.filter(Task.book_id == book_id)
        t = q.order_by(Task.created_at.desc()).first()
        return to_dict(t) if t else None


def find_latest(
    user_id: str, task_type: str, book_id: Optional[str] = None,
) -> Optional[dict]:
    """前端展示用: 最近一次任务 (任意状态)."""
    with get_db() as db:
        q = db.query(Task).filter_by(user_id=user_id, task_type=task_type)
        if book_id is not None:
            q = q.filter(Task.book_id == book_id)
        t = q.order_by(Task.created_at.desc()).first()
        return to_dict(t) if t else None


# ---------- 僵尸清理 ----------

def cleanup_zombies(
    stale_seconds: int = 3600,
    is_alive: Optional[Callable[[dict], bool]] = None,
) -> int:
    """启动时调用. running 但 created_at 超阈值的任务 -> failed.

    A2A 用 InMemoryTaskStore, agent-server 进程重启就丢任务, DB 留着的
    running 会一直挡用户; 用超时兜底.

    is_alive 可选: 给一个 callback (Task dict) -> bool, 还活着就跳过不杀,
    避免误伤超长任务 (大书 LLM 跑 >1h 仍在工作). callback 异常视为死.
    """
    threshold = datetime.utcnow() - timedelta(seconds=stale_seconds)
    killed = 0
    skipped = 0
    with get_db() as db:
        candidates = (
            db.query(Task)
            .filter(Task.status == "running", Task.created_at < threshold)
            .all()
        )
        for t in candidates:
            if is_alive:
                try:
                    if is_alive(to_dict(t)):
                        skipped += 1
                        continue
                except Exception as e:
                    logger.debug(f"is_alive check raised, treating as dead: {e}")
            t.status = "failed"
            t.message = "服务重启或任务超时, 进程已不存在"
            t.finished_at = datetime.utcnow()
            killed += 1
        db.commit()
    if killed or skipped:
        logger.info(f"tasks.cleanup_zombies: killed={killed} skipped_alive={skipped}")
    return killed
