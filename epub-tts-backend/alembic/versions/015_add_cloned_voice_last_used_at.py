"""Add last_used_at to cloned_voices"""
from alembic import op
import sqlalchemy as sa

revision = "015_add_clone_voice_used_at"
down_revision = "014_add_system_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cloned_voices",
        sa.Column("last_used_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
    )


def downgrade():
    op.drop_column("cloned_voices", "last_used_at")
