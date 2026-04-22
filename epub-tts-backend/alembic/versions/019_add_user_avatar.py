"""Add avatar_url to users table

Revision ID: 019_add_user_avatar
Revises: 018_add_initial_definition
Create Date: 2026-04-22

"""
from alembic import op
import sqlalchemy as sa


revision = "019_add_user_avatar"
down_revision = "018_add_initial_definition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users",
                  sa.Column("avatar_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
