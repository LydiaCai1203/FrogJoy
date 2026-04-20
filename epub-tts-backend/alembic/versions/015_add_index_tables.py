"""Add Index Layer tables: indexed_books + indexed_paragraphs

这是 Book Language Server 索引化的地基。
详细设计: docs/book-as-indexed-knowledge-base.md §6

v0 只建最必要的两张表, concepts / occurrences / relations 等待 Extractor (LLM)
接入后追加。

Revision ID: 015_add_index_tables
Revises: 014_add_system_settings
Create Date: 2026-04-20

"""
from alembic import op
import sqlalchemy as sa


revision = "015_add_index_tables"
down_revision = "014_add_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- indexed_books ----------
    op.create_table(
        "indexed_books",
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("book_fingerprint", sa.String(), nullable=False),
        sa.Column("total_chapters", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("total_paragraphs", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("status", sa.String(), nullable=False,
                  server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("index_version", sa.String(), nullable=False,
                  server_default="v0"),
        sa.Column("parsed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(),
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("book_id", "user_id"),
    )
    op.create_index(
        "idx_indexed_books_user", "indexed_books", ["user_id"],
    )
    op.create_index(
        "idx_indexed_books_fingerprint",
        "indexed_books",
        ["book_fingerprint"],
    )

    # ---------- indexed_paragraphs ----------
    op.create_table(
        "indexed_paragraphs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("chapter_idx", sa.Integer(), nullable=False),
        sa.Column("chapter_title", sa.String(), nullable=True),
        sa.Column("chapter_fp", sa.String(), nullable=False),
        sa.Column("para_idx_in_chapter", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(),
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_iparagraphs_user_book",
        "indexed_paragraphs",
        ["user_id", "book_id"],
    )
    op.create_index(
        "idx_iparagraphs_user_book_chapter",
        "indexed_paragraphs",
        ["user_id", "book_id", "chapter_idx"],
    )


def downgrade() -> None:
    op.drop_index("idx_iparagraphs_user_book_chapter",
                  table_name="indexed_paragraphs")
    op.drop_index("idx_iparagraphs_user_book",
                  table_name="indexed_paragraphs")
    op.drop_table("indexed_paragraphs")

    op.drop_index("idx_indexed_books_fingerprint",
                  table_name="indexed_books")
    op.drop_index("idx_indexed_books_user",
                  table_name="indexed_books")
    op.drop_table("indexed_books")
