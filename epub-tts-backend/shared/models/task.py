from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index, func

from shared.models import Base


class Task(Base):
    """通用后台任务表.

    一条记录代表一次"用户触发的后台作业" — 当前用于概念抽取, 将来会承载
    索引构建 / 翻译 / TTS 批处理等. 不强制外键到 book, 删书时不连锁.

    状态机: running -> {completed, failed, cancelled}
      - 没有 pending: agent-server kickoff 是同步的, 进库时已经在跑
      - completed/failed/cancelled 都是终态, 写入 finished_at

    message 字段三用 (运行中=阶段描述, 完成=总结, 失败=错误原因), 避免把
    error_message / result 拆成多列.
    """
    __tablename__ = "tasks"

    id           = Column(String, primary_key=True)                          # task:{uuid4}
    user_id      = Column(String, ForeignKey("users.id"), nullable=False)
    book_id      = Column(String, nullable=True)                             # 关联书, 不强 FK

    task_type    = Column(String, nullable=False)                            # concept_extraction / index_build / ...

    status       = Column(String, nullable=False, server_default="running")  # running/completed/failed/cancelled
    progress     = Column(Integer, nullable=False, server_default="0")
    message      = Column(Text, nullable=True)                               # 运行/完成/失败 单字段三用

    external_id  = Column(String, nullable=True)                             # A2A task_id 等

    created_at   = Column(DateTime, server_default=func.now())
    finished_at  = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_tasks_user_status", "user_id", "status"),
        Index("idx_tasks_book_type", "book_id", "task_type"),
    )
