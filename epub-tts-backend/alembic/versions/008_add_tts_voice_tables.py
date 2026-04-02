"""Add TTS and voice related tables

Revision ID: 008_add_tts_voice_tables
Revises: 007_update_null_font_size
Create Date: 2026-04-01

"""
from alembic import op
import sqlalchemy as sa


revision = "008_add_tts_voice_tables"
down_revision = "007_update_null_font_size"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TTSProviderConfig
    op.create_table(
        "tts_provider_configs",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("provider_type", sa.String(), nullable=False, server_default="edge-tts"),
        sa.Column("base_url", sa.String(), nullable=True),
        sa.Column("api_key_encrypted", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ClonedVoice
    op.create_table(
        "cloned_voices",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("voice_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("audio_sample_path", sa.String(), nullable=False),
        sa.Column("lang", sa.String(), server_default="zh"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_cloned_voices_user", "cloned_voices", ["user_id"])

    # VoicePreferences
    op.create_table(
        "voice_preferences",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("active_voice_type", sa.String(), server_default="edge"),
        sa.Column("active_edge_voice", sa.String(), server_default="zh-CN-XiaoxiaoNeural"),
        sa.Column("active_minimax_voice", sa.String(), nullable=True),
        sa.Column("active_cloned_voice_id", sa.String(), nullable=True),
        sa.Column("speed", sa.Integer(), server_default=sa.text("100")),
        sa.Column("pitch", sa.Integer(), server_default=sa.text("0")),
        sa.Column("emotion", sa.String(), server_default="neutral"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # UserFeatureSetup
    op.create_table(
        "user_feature_setup",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("ai_chat_configured", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("ai_translation_configured", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("voice_selection_configured", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("voice_synthesis_configured", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_feature_setup")
    op.drop_table("voice_preferences")
    op.drop_index("idx_cloned_voices_user", table_name="cloned_voices")
    op.drop_table("cloned_voices")
    op.drop_table("tts_provider_configs")
