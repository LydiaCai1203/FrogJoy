"""Evidence-grounded concept extraction

加 concepts.parent_concept_id 显式建模上下位关系.
新增 concept_evidence 表存 LLM 给的 verbatim quote, 替代靠 Phase 3
regex 推断 definition/refinement 的旧做法.

Revision ID: 021_evidence_grounded_concepts
Revises: 020_add_user_name
Create Date: 2026-04-27

"""
from alembic import op
import sqlalchemy as sa


revision = "021_evidence_grounded_concepts"
down_revision = "020_add_user_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- concepts.parent_concept_id ----------
    op.add_column(
        "concepts",
        sa.Column("parent_concept_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_concepts_parent",
        "concepts",
        "concepts",
        ["parent_concept_id"],
        ["id"],
    )
    op.create_index("idx_concepts_parent", "concepts", ["parent_concept_id"])

    # ---------- concept_evidence ----------
    op.create_table(
        "concept_evidence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("concept_id", sa.String(), nullable=False),
        sa.Column("paragraph_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("chapter_idx", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("char_offset", sa.Integer(), nullable=False),
        sa.Column("char_length", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"]),
        sa.ForeignKeyConstraint(["paragraph_id"], ["indexed_paragraphs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ev_user_book", "concept_evidence",
                    ["user_id", "book_id"])
    op.create_index("idx_ev_user_book_chapter", "concept_evidence",
                    ["user_id", "book_id", "chapter_idx"])
    op.create_index("idx_ev_concept", "concept_evidence", ["concept_id"])
    op.create_index("idx_ev_paragraph", "concept_evidence", ["paragraph_id"])


def downgrade() -> None:
    op.drop_index("idx_ev_paragraph", table_name="concept_evidence")
    op.drop_index("idx_ev_concept", table_name="concept_evidence")
    op.drop_index("idx_ev_user_book_chapter", table_name="concept_evidence")
    op.drop_index("idx_ev_user_book", table_name="concept_evidence")
    op.drop_table("concept_evidence")

    op.drop_index("idx_concepts_parent", table_name="concepts")
    op.drop_constraint("fk_concepts_parent", "concepts", type_="foreignkey")
    op.drop_column("concepts", "parent_concept_id")
