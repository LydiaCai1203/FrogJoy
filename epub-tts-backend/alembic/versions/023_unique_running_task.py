"""Unique partial index: 同 (user, type, book) 只能一个 running 任务

数据库层面挡住 build_concepts 那条 TOCTOU 竞态: find_running 与 create 之间
另一并发请求溜进去导致两条 running 行存在. 加完之后 tasks.create 撞 unique
违反时 IntegrityError 被业务层捕获, 重新读 find_running 即可.

Revision ID: 023_unique_running_task
Revises: 022_add_tasks_table
Create Date: 2026-04-27

"""
from alembic import op
import sqlalchemy as sa


revision = "023_unique_running_task"
down_revision = "022_add_tasks_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 加之前先把残留的重复 running 行清掉, 否则 unique 索引创建会失败.
    # 同 (user_id, task_type, book_id) 多条 running 时, 保留 created_at 最新的
    # 一条, 其余标 cancelled (非破坏性).
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id, task_type, COALESCE(book_id, '')
                       ORDER BY created_at DESC
                   ) AS rn
            FROM tasks
            WHERE status = 'running'
        )
        UPDATE tasks
        SET status = 'cancelled',
            message = '清理 unique 约束前的重复 running 记录',
            finished_at = NOW()
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    # Postgres 部分唯一索引: 仅 status='running' 的行参与唯一性约束
    op.create_index(
        "uq_tasks_running",
        "tasks",
        ["user_id", "task_type", "book_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("uq_tasks_running", table_name="tasks")
