"""Add translation_prompt to user_ai_preferences

Revision ID: 005_add_translation_prompt
Revises: 004_add_theme
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa


revision = "005_add_translation_prompt"
down_revision = "004_add_theme"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_ai_preferences", sa.Column("translation_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_ai_preferences", "translation_prompt")
