"""add final vers

Revision ID: faf358c997a4
Revises: 72ee1bb5936a
Create Date: 2025-04-17 09:18:40.910480

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'faf358c997a4'
down_revision: Union[str, None] = '72ee1bb5936a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('goal_stats_final',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('counter_id', sa.BigInteger(), nullable=False),
    sa.Column('goal_id', sa.BigInteger(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('period_type', sa.String(), nullable=False),
    sa.Column('reaches', sa.Integer(), nullable=False),
    sa.Column('conversion_rate', sa.Float(), nullable=False),
    sa.Column('visits', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('counter_id', 'goal_id', 'date', 'period_type', name='uix_counter_goal_date_period')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('goal_stats_final')
    # ### end Alembic commands ###
