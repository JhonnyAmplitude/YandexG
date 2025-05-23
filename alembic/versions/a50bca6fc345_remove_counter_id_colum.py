"""Remove counter_id colum

Revision ID: a50bca6fc345
Revises: 8031e92a930e
Create Date: 2025-04-17 09:35:03.997385

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a50bca6fc345'
down_revision: Union[str, None] = '8031e92a930e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('uix_counter_goal_date_period', 'goal_stats_final', type_='unique')
    op.create_unique_constraint('uix_counter_goal_date_period', 'goal_stats_final', ['goal_id', 'date', 'period_type'])
    op.drop_column('goal_stats_final', 'counter_id')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('goal_stats_final', sa.Column('counter_id', sa.BIGINT(), autoincrement=False, nullable=False))
    op.drop_constraint('uix_counter_goal_date_period', 'goal_stats_final', type_='unique')
    op.create_unique_constraint('uix_counter_goal_date_period', 'goal_stats_final', ['counter_id', 'goal_id', 'date', 'period_type'])
    # ### end Alembic commands ###
