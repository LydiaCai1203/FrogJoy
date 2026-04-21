"""Add initial_definition to concepts table

Revision ID: 018_add_initial_definition
Revises: 017_add_concept_tables
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa


revision = "018_add_initial_definition"
down_revision = "017_add_concept_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("concepts",
                  sa.Column("initial_definition", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("concepts", "initial_definition")
