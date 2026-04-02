"""Add is_admin column to users

Revision ID: 012_add_user_is_admin
Revises: 011_add_user_verification
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa


revision = "012_add_user_is_admin"
down_revision = "011_add_user_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
