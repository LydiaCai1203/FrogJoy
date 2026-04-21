"""Merge preference tables, fix reading_stats.date, normalize AI configs

1. Merge user_theme_preferences + voice_preferences + user_ai_preferences
   + user_feature_setup → user_preferences
2. Fix reading_stats.date from String → Date
3. Normalize ai_model_configs → ai_provider_configs

Revision ID: 016_refactor_preferences_and_ai
Revises: 015_add_index_tables
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa


revision = "016_refactor_preferences_and_ai"
down_revision = "015_add_index_tables"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Merge 4 preference tables → user_preferences                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "user_preferences",
        # PK / FK
        sa.Column("user_id", sa.String(), nullable=False),
        # from user_theme_preferences
        sa.Column("theme", sa.String(), nullable=True, server_default="eye-care"),
        sa.Column("font_size", sa.Integer(), nullable=True, server_default="18"),
        # from voice_preferences
        sa.Column("active_voice_type", sa.String(), nullable=True, server_default="edge"),
        sa.Column("active_edge_voice", sa.String(), nullable=True,
                  server_default="zh-CN-XiaoxiaoNeural"),
        sa.Column("active_minimax_voice", sa.String(), nullable=True),
        sa.Column("active_cloned_voice_id", sa.String(), nullable=True),
        sa.Column("speed", sa.Integer(), nullable=True, server_default="100"),
        sa.Column("pitch", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("emotion", sa.String(), nullable=True, server_default="neutral"),
        sa.Column("audio_persistent", sa.Boolean(), nullable=True, server_default="false"),
        # from user_ai_preferences
        sa.Column("enabled_ask_ai", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("enabled_translation", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("translation_mode", sa.String(), nullable=True,
                  server_default="current-page"),
        sa.Column("source_lang", sa.String(), nullable=True, server_default="Auto"),
        sa.Column("target_lang", sa.String(), nullable=True, server_default="Chinese"),
        sa.Column("translation_prompt", sa.Text(), nullable=True),
        # timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Migrate data: one row per user using LEFT JOINs on all 4 old tables
    op.execute("""
        INSERT INTO user_preferences (
            user_id,
            theme, font_size,
            active_voice_type, active_edge_voice, active_minimax_voice,
            active_cloned_voice_id, speed, pitch, emotion, audio_persistent,
            enabled_ask_ai, enabled_translation, translation_mode,
            source_lang, target_lang, translation_prompt,
            created_at, updated_at
        )
        SELECT
            u.id,
            COALESCE(tp.theme, 'eye-care'),
            COALESCE(tp.font_size, 18),
            COALESCE(vp.active_voice_type, 'edge'),
            COALESCE(vp.active_edge_voice, 'zh-CN-XiaoxiaoNeural'),
            vp.active_minimax_voice,
            vp.active_cloned_voice_id,
            COALESCE(vp.speed, 100),
            COALESCE(vp.pitch, 0),
            COALESCE(vp.emotion, 'neutral'),
            COALESCE(vp.audio_persistent, false),
            COALESCE(ap.enabled_ask_ai, false),
            COALESCE(ap.enabled_translation, false),
            COALESCE(ap.translation_mode, 'current-page'),
            COALESCE(ap.source_lang, 'Auto'),
            COALESCE(ap.target_lang, 'Chinese'),
            ap.translation_prompt,
            COALESCE(vp.created_at, NOW()),
            GREATEST(tp.updated_at, vp.updated_at, ap.updated_at)
        FROM users u
        LEFT JOIN user_theme_preferences tp ON tp.user_id = u.id
        LEFT JOIN voice_preferences      vp ON vp.user_id = u.id
        LEFT JOIN user_ai_preferences    ap ON ap.user_id = u.id
    """)

    # Drop the 4 old preference tables
    op.drop_table("user_feature_setup")
    op.drop_table("user_ai_preferences")
    op.drop_table("voice_preferences")
    op.drop_table("user_theme_preferences")

    # ------------------------------------------------------------------ #
    # 2. Fix reading_stats.date: String → Date                           #
    # ------------------------------------------------------------------ #
    op.execute(
        "ALTER TABLE reading_stats ALTER COLUMN date TYPE date USING date::date"
    )

    # ------------------------------------------------------------------ #
    # 3. Normalize ai_model_configs → ai_provider_configs                #
    # ------------------------------------------------------------------ #
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("provider_type", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("api_key_encrypted", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "purpose", name="uq_ai_provider_user_purpose"),
    )
    op.create_index(
        "idx_ai_provider_configs_user_id",
        "ai_provider_configs",
        ["user_id"],
    )

    # Migrate chat rows (every row in ai_model_configs has a chat config)
    op.execute("""
        INSERT INTO ai_provider_configs (
            id, user_id, purpose, provider_type, base_url,
            api_key_encrypted, model, created_at, updated_at
        )
        SELECT
            gen_random_uuid()::text,
            user_id,
            'chat',
            provider_type,
            base_url,
            api_key_encrypted,
            model,
            created_at,
            updated_at
        FROM ai_model_configs
    """)

    # Migrate translation rows (only when all 4 translation_* fields are non-null)
    op.execute("""
        INSERT INTO ai_provider_configs (
            id, user_id, purpose, provider_type, base_url,
            api_key_encrypted, model, created_at, updated_at
        )
        SELECT
            gen_random_uuid()::text,
            user_id,
            'translation',
            translation_provider_type,
            translation_base_url,
            translation_api_key_encrypted,
            translation_model,
            created_at,
            updated_at
        FROM ai_model_configs
        WHERE
            translation_provider_type       IS NOT NULL
            AND translation_base_url        IS NOT NULL
            AND translation_api_key_encrypted IS NOT NULL
            AND translation_model           IS NOT NULL
    """)

    op.drop_table("ai_model_configs")


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # ------------------------------------------------------------------ #
    # 3. Restore ai_model_configs from ai_provider_configs               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "ai_model_configs",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider_type", sa.String(), nullable=False, server_default="openai-chat"),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("api_key_encrypted", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("translation_provider_type", sa.String(), nullable=True),
        sa.Column("translation_base_url", sa.String(), nullable=True),
        sa.Column("translation_api_key_encrypted", sa.String(), nullable=True),
        sa.Column("translation_model", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Restore chat rows first (one row per user from 'chat' purpose)
    op.execute("""
        INSERT INTO ai_model_configs (
            user_id, provider_type, base_url, api_key_encrypted,
            model, created_at, updated_at
        )
        SELECT
            user_id, provider_type, base_url, api_key_encrypted,
            model, created_at, updated_at
        FROM ai_provider_configs
        WHERE purpose = 'chat'
    """)

    # Restore translation fields by updating from 'translation' rows
    op.execute("""
        UPDATE ai_model_configs mc
        SET
            translation_provider_type       = tr.provider_type,
            translation_base_url            = tr.base_url,
            translation_api_key_encrypted   = tr.api_key_encrypted,
            translation_model               = tr.model
        FROM ai_provider_configs tr
        WHERE tr.user_id = mc.user_id
          AND tr.purpose = 'translation'
    """)

    op.drop_index("idx_ai_provider_configs_user_id",
                  table_name="ai_provider_configs")
    op.drop_table("ai_provider_configs")

    # ------------------------------------------------------------------ #
    # 2. Restore reading_stats.date: Date → String (varchar)             #
    # ------------------------------------------------------------------ #
    op.execute(
        "ALTER TABLE reading_stats ALTER COLUMN date TYPE varchar USING date::text"
    )

    # ------------------------------------------------------------------ #
    # 1. Restore 4 preference tables from user_preferences               #
    # ------------------------------------------------------------------ #

    # user_theme_preferences
    op.create_table(
        "user_theme_preferences",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("theme", sa.String(), nullable=True, server_default="eye-care"),
        sa.Column("font_size", sa.Integer(), nullable=True, server_default="18"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.execute("""
        INSERT INTO user_theme_preferences (user_id, theme, font_size, updated_at)
        SELECT user_id, theme, font_size, updated_at
        FROM user_preferences
    """)

    # voice_preferences
    op.create_table(
        "voice_preferences",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("active_voice_type", sa.String(), nullable=True, server_default="edge"),
        sa.Column("active_edge_voice", sa.String(), nullable=True,
                  server_default="zh-CN-XiaoxiaoNeural"),
        sa.Column("active_minimax_voice", sa.String(), nullable=True),
        sa.Column("active_cloned_voice_id", sa.String(), nullable=True),
        sa.Column("speed", sa.Integer(), nullable=True, server_default="100"),
        sa.Column("pitch", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("emotion", sa.String(), nullable=True, server_default="neutral"),
        sa.Column("audio_persistent", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.execute("""
        INSERT INTO voice_preferences (
            user_id, active_voice_type, active_edge_voice, active_minimax_voice,
            active_cloned_voice_id, speed, pitch, emotion, audio_persistent,
            created_at, updated_at
        )
        SELECT
            user_id, active_voice_type, active_edge_voice, active_minimax_voice,
            active_cloned_voice_id, speed, pitch, emotion, audio_persistent,
            created_at, updated_at
        FROM user_preferences
    """)

    # user_ai_preferences
    op.create_table(
        "user_ai_preferences",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("enabled_ask_ai", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("enabled_translation", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("translation_mode", sa.String(), nullable=True,
                  server_default="current-page"),
        sa.Column("source_lang", sa.String(), nullable=True, server_default="Auto"),
        sa.Column("target_lang", sa.String(), nullable=True, server_default="Chinese"),
        sa.Column("translation_prompt", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.execute("""
        INSERT INTO user_ai_preferences (
            user_id, enabled_ask_ai, enabled_translation, translation_mode,
            source_lang, target_lang, translation_prompt, updated_at
        )
        SELECT
            user_id, enabled_ask_ai, enabled_translation, translation_mode,
            source_lang, target_lang, translation_prompt, updated_at
        FROM user_preferences
    """)

    # user_feature_setup — recreate empty (no data to restore; was not migrated)
    op.create_table(
        "user_feature_setup",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("ai_chat_configured", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("ai_translation_configured", sa.Boolean(), nullable=True,
                  server_default="false"),
        sa.Column("voice_selection_configured", sa.Boolean(), nullable=True,
                  server_default="false"),
        sa.Column("voice_synthesis_configured", sa.Boolean(), nullable=True,
                  server_default="false"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.drop_table("user_preferences")
