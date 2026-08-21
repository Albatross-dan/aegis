"""add rejected_ticks quarantine table

Revision ID: bc3df868b6b8
Revises: 58716bcd0548
Create Date: 2026-08-17 06:47:37.107420
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bc3df868b6b8'
down_revision: Union[str, Sequence[str], None] = '58716bcd0548'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rejected_ticks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("symbol", sa.String(length=20), nullable=True),
        sa.Column("broker_symbol", sa.String(length=20), nullable=True),
        sa.Column("bid", sa.Numeric(), nullable=True),
        sa.Column("ask", sa.Numeric(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("rejection_reason", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rejected_ticks_received_at", "rejected_ticks", ["received_at"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rejected_ticks_received_at", table_name="rejected_ticks")
    op.drop_table("rejected_ticks")
