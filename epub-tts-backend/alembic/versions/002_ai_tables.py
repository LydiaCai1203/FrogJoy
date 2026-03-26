"""Add AI model config, preferences, and book translations

Revision ID: 002_ai_tables
Revises: 001
Create Date: 2026-03-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "002_ai_tables"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AI Model Config
    op.create_table(
        "ai_model_configs",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider_type", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("api_key_encrypted", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # User AI Preferences
    op.create_table(
        "user_ai_preferences",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("enabled_ask_ai", sa.Boolean(), nullable=True, default=False),
        sa.Column("enabled_translation", sa.Boolean(), nullable=True, default=False),
        sa.Column("translation_mode", sa.String(), nullable=True, default="current-page"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Book Translations
    op.create_table(
        "book_translations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("chapter_href", sa.String(), nullable=False),
        sa.Column("original_content", sa.Text(), nullable=True),
        sa.Column("translated_content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=True, default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "book_id", "chapter_href", name="uq_translation_user_book_chapter"),
    )

    op.create_index("idx_translation_book", "book_translations", ["user_id", "book_id"])


def downgrade() -> None:
    op.drop_index("idx_translation_book", table_name="book_translations")
    op.drop_table("book_translations")
    op.drop_table("user_ai_preferences")
    op.drop_table("ai_model_configs")
