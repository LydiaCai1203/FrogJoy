"""Add chapter_index and total_chapters to reading_progress

Avoid expensive EPUB parsing on every /api/books call by caching
the chapter position when saving reading progress.

Revision ID: 024_read_progress_chapters
Revises: 023_unique_running_task
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa


revision = "024_read_progress_chapters"
down_revision = "023_unique_running_task"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reading_progress",
        sa.Column("chapter_index", sa.Integer, nullable=True),
    )
    op.add_column(
        "reading_progress",
        sa.Column("total_chapters", sa.Integer, nullable=True),
    )


def downgrade():
    op.drop_column("reading_progress", "total_chapters")
    op.drop_column("reading_progress", "chapter_index")
