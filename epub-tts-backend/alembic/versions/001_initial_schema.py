"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "books",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("creator", sa.String()),
        sa.Column("cover_url", sa.String()),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_opened_at", sa.DateTime()),
    )
    op.create_index("idx_books_user_id", "books", ["user_id"])
    op.create_index("idx_books_is_public", "books", ["is_public"])

    op.create_table(
        "highlights",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("chapter_href", sa.String(), nullable=False),
        sa.Column("paragraph_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("end_paragraph_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("start_offset", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("end_offset", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("selected_text", sa.Text(), nullable=False),
        sa.Column("color", sa.String(), nullable=False, server_default=sa.text("'yellow'")),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_highlights_book_chapter", "highlights", ["book_id", "chapter_href"])
    op.create_index("idx_highlights_user_book", "highlights", ["user_id", "book_id"])

    op.create_table(
        "reading_stats",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "book_id", "date", name="uq_reading_stats_user_book_date"),
    )
    op.create_index("idx_reading_stats_user_date", "reading_stats", ["user_id", "date"])
    op.create_index("idx_reading_stats_user_book", "reading_stats", ["user_id", "book_id"])

    op.create_table(
        "reading_progress",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("book_id", sa.String(), sa.ForeignKey("books.id"), primary_key=True),
        sa.Column("chapter_href", sa.String(), nullable=False),
        sa.Column("paragraph_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("reading_progress")
    op.drop_table("reading_stats")
    op.drop_table("highlights")
    op.drop_table("books")
    op.drop_table("users")
