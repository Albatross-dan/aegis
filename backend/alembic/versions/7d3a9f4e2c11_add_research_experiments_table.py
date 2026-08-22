"""add research_experiments table

Revision ID: 7d3a9f4e2c11
Revises: 1c2143637922
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d3a9f4e2c11'
down_revision: Union[str, Sequence[str], None] = '1c2143637922'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "research_experiments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("experiment_name", sa.String(length=120), nullable=False),
        sa.Column("run_type", sa.String(length=50), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_experiments_name_created_at",
        "research_experiments",
        ["experiment_name", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_research_experiments_name_created_at", table_name="research_experiments")
    op.drop_table("research_experiments")