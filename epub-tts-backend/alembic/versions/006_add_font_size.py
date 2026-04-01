"""Add font_size to user_theme_preferences

Revision ID: 006_add_font_size
Revises: 005_add_translation_prompt
Create Date: 2026-04-01

"""
from alembic import op
import sqlalchemy as sa


revision = "006_add_font_size"
down_revision = "005_add_translation_prompt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_theme_preferences", sa.Column("font_size", sa.Integer(), nullable=False, server_default="18"))


def downgrade() -> None:
    op.drop_column("user_theme_preferences", "font_size")