"""add technical_features table

Revision ID: 18c92d130b3c
Revises: a572d49948a2
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18c92d130b3c'
down_revision: Union[str, Sequence[str], None] = 'a572d49948a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "technical_features",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sma_20", sa.Float(), nullable=True),
        sa.Column("ema_20", sa.Float(), nullable=True),
        sa.Column("rsi_14", sa.Float(), nullable=True),
        sa.Column("atr_14", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_technical_features_symbol_bucket",
        "technical_features",
        ["symbol", "bucket"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_technical_features_symbol_bucket", table_name="technical_features")
    op.drop_table("technical_features")
