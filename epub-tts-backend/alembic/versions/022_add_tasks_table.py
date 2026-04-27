"""Add generic background tasks table

通用后台任务表, 当前承载概念抽取, 将来给索引构建 / 翻译 / TTS 批处理共用.

Revision ID: 022_add_tasks_table
Revises: 021_evidence_grounded_concepts
Create Date: 2026-04-27

"""
from alembic import op
import sqlalchemy as sa


revision = "022_add_tasks_table"
down_revision = "021_evidence_grounded_concepts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("book_id", sa.String(), nullable=True),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tasks_user_status", "tasks", ["user_id", "status"])
    op.create_index("idx_tasks_book_type", "tasks", ["book_id", "task_type"])


def downgrade() -> None:
    op.drop_index("idx_tasks_book_type", table_name="tasks")
    op.drop_index("idx_tasks_user_status", table_name="tasks")
    op.drop_table("tasks")
