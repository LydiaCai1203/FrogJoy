"""Add is_verified column to users

Revision ID: 011_add_user_verification
Revises: 010_add_audio_persistent
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa


revision = "011_add_user_verification"
down_revision = "010_add_audio_persistent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_verified")
