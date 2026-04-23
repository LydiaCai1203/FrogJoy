"""Add name column to users table

Revision ID: 020_add_user_name
Revises: 019_add_user_avatar
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa


revision = "020_add_user_name"
down_revision = "019_add_user_avatar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users",
                  sa.Column("name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "name")
