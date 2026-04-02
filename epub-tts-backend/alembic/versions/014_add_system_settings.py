"""Add system_settings table for admin-managed configuration

Revision ID: 014_add_system_settings
Revises: 013_user_last_login_active
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa


revision = "014_add_system_settings"
down_revision = "013_user_last_login_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    # Seed defaults
    op.execute(
        "INSERT INTO system_settings (key, value) VALUES "
        "('guest_rate_limit_tts', '5'), "
        "('guest_rate_limit_translation', '1'), "
        "('guest_rate_limit_chat', '1'), "
        "('default_tts_provider', 'edge-tts'), "
        "('default_theme', 'eye-care'), "
        "('default_font_size', '18'), "
        "('allow_registration', 'true')"
    )


def downgrade() -> None:
    op.drop_table("system_settings")
