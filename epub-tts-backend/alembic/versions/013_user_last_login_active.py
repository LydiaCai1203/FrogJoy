"""Add last_login_at and is_active columns to users

Revision ID: 013_add_user_last_login_and_active
Revises: 012_add_user_is_admin
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa


revision = "013_user_last_login_active"
down_revision = "012_add_user_is_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_active")
