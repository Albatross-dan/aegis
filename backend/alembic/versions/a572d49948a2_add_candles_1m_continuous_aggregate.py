"""add candles_1m continuous aggregate

Revision ID: a572d49948a2
Revises: bc3df868b6b8
Create Date: 2026-08-18 12:07:26.657871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a572d49948a2'
down_revision: Union[str, Sequence[str], None] = 'bc3df868b6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE MATERIALIZED VIEW candles_1m
            WITH (timescaledb.continuous) AS
            SELECT
                symbol,
                time_bucket('1 minute', timestamp) AS bucket,
                first(bid, timestamp) AS open,
                max(bid) AS high,
                min(bid) AS low,
                last(bid, timestamp) AS close,
                count(*) AS tick_count
            FROM market_ticks
            GROUP BY symbol, bucket
            WITH NO DATA;
        """)

        op.execute("""
            SELECT add_continuous_aggregate_policy('candles_1m',
                start_offset => INTERVAL '3 hours',
                end_offset => INTERVAL '1 minute',
                schedule_interval => INTERVAL '1 minute');
        """)


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("DROP MATERIALIZED VIEW IF EXISTS candles_1m CASCADE;")
