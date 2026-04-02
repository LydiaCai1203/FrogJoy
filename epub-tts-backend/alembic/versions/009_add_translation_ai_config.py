"""Add translation-specific AI config fields to ai_model_configs

Revision ID: 009_add_translation_ai_config
Revises: 008_add_tts_voice_tables
Create Date: 2026-04-01

"""
from alembic import op
import sqlalchemy as sa


revision = "009_add_translation_ai_config"
down_revision = "008_add_tts_voice_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_model_configs", sa.Column("translation_provider_type", sa.String(), nullable=True))
    op.add_column("ai_model_configs", sa.Column("translation_base_url", sa.String(), nullable=True))
    op.add_column("ai_model_configs", sa.Column("translation_api_key_encrypted", sa.String(), nullable=True))
    op.add_column("ai_model_configs", sa.Column("translation_model", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_model_configs", "translation_model")
    op.drop_column("ai_model_configs", "translation_api_key_encrypted")
    op.drop_column("ai_model_configs", "translation_base_url")
    op.drop_column("ai_model_configs", "translation_provider_type")
