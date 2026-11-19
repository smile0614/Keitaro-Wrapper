from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('campaigns',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('keitaro_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('alias', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_campaigns_keitaro_id'), ['keitaro_id'], unique=True)

    op.create_table('streams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('keitaro_id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('has_offers', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('streams', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_streams_keitaro_id'), ['keitaro_id'], unique=True)

    op.create_table('stream_offers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('stream_id', sa.Integer(), nullable=False),
    sa.Column('offer_id', sa.Integer(), nullable=False),
    sa.Column('offer_name', sa.String(length=500), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('share', sa.Integer(), nullable=False),
    sa.Column('pinned', sa.Boolean(), nullable=False),
    sa.Column('published_state', sa.String(length=16), nullable=True),
    sa.Column('published_share', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['stream_id'], ['streams.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stream_id', 'offer_id')
    )


def downgrade() -> None:
    op.drop_table('stream_offers')
    with op.batch_alter_table('streams', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_streams_keitaro_id'))

    op.drop_table('streams')
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campaigns_keitaro_id'))

    op.drop_table('campaigns')
