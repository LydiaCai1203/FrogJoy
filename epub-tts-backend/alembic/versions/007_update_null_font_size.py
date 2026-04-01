"""Update NULL font_size to default 18

Revision ID: 007_update_null_font_size
Revises: 006_add_font_size
Create Date: 2026-04-01

"""
from alembic import op
import sqlalchemy as sa


revision = "007_update_null_font_size"
down_revision = "006_add_font_size"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE user_theme_preferences SET font_size = 18 WHERE font_size IS NULL")


def downgrade() -> None:
    pass