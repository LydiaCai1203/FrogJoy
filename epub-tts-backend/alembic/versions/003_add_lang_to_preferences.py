"""Add source_lang and target_lang to user_ai_preferences

Revision ID: 003_add_lang
Revises: 002_ai_tables
Create Date: 2026-03-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "003_add_lang"
down_revision = "002_ai_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_ai_preferences", sa.Column("source_lang", sa.String(), nullable=True, server_default="Auto"))
    op.add_column("user_ai_preferences", sa.Column("target_lang", sa.String(), nullable=True, server_default="Chinese"))


def downgrade() -> None:
    op.drop_column("user_ai_preferences", "target_lang")
    op.drop_column("user_ai_preferences", "source_lang")
