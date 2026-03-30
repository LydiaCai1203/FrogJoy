"""Add user_theme_preferences table

Revision ID: 004_add_theme
Revises: 003_add_lang
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa


revision = "004_add_theme"
down_revision = "003_add_lang"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_theme_preferences",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("theme", sa.String(), nullable=False, server_default="eye-care"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("user_theme_preferences")
