"""Add concept extraction tables: concepts + concept_occurrences

概念提取层: 在 indexed_paragraphs 之上构建概念网络。
设计文档: docs/concept-extraction-and-hover-design.md

Revision ID: 017_add_concept_tables
Revises: 016_refactor_preferences_and_ai
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa


revision = "017_add_concept_tables"
down_revision = "016_refactor_preferences_and_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- concepts ----------
    op.create_table(
        "concepts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("term", sa.String(), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("total_occurrences", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("chapter_count", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("scope", sa.String(), nullable=False,
                  server_default="chapter"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_concepts_user_book", "concepts",
                    ["user_id", "book_id"])

    # ---------- concept_occurrences ----------
    op.create_table(
        "concept_occurrences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("concept_id", sa.String(), nullable=False),
        sa.Column("paragraph_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("chapter_idx", sa.Integer(), nullable=False),
        sa.Column("occurrence_type", sa.String(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("core_sentence", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"]),
        sa.ForeignKeyConstraint(["paragraph_id"], ["indexed_paragraphs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_occ_user_book", "concept_occurrences",
                    ["user_id", "book_id"])
    op.create_index("idx_occ_concept", "concept_occurrences",
                    ["concept_id"])
    op.create_index("idx_occ_paragraph", "concept_occurrences",
                    ["paragraph_id"])
    op.create_index("idx_occ_user_book_chapter", "concept_occurrences",
                    ["user_id", "book_id", "chapter_idx"])

    # ---------- indexed_books 扩展 ----------
    op.add_column("indexed_books",
                  sa.Column("concept_status", sa.String(), nullable=True))
    op.add_column("indexed_books",
                  sa.Column("concept_error", sa.Text(), nullable=True))
    op.add_column("indexed_books",
                  sa.Column("total_concepts", sa.Integer(), nullable=False,
                            server_default="0"))


def downgrade() -> None:
    op.drop_column("indexed_books", "total_concepts")
    op.drop_column("indexed_books", "concept_error")
    op.drop_column("indexed_books", "concept_status")

    op.drop_index("idx_occ_user_book_chapter",
                  table_name="concept_occurrences")
    op.drop_index("idx_occ_paragraph", table_name="concept_occurrences")
    op.drop_index("idx_occ_concept", table_name="concept_occurrences")
    op.drop_index("idx_occ_user_book", table_name="concept_occurrences")
    op.drop_table("concept_occurrences")

    op.drop_index("idx_concepts_user_book", table_name="concepts")
    op.drop_table("concepts")
