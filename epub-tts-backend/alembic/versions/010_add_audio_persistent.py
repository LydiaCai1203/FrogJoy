"""Add audio_persistent column to voice_preferences

Revision ID: 010_add_audio_persistent
Revises: 009_add_translation_ai_config
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa


revision = "010_add_audio_persistent"
down_revision = "009_add_translation_ai_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "voice_preferences",
        sa.Column("audio_persistent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("voice_preferences", "audio_persistent")
