"""Provisioned local IBKR sync credentials."""
from alembic import op
import sqlalchemy as sa
revision='b2c3d4e5f6a7';down_revision='a1b2c3d4e5f6';branch_labels=depends_on=None
def upgrade():
 if op.get_bind().dialect.name=='sqlite':
  with op.batch_alter_table('brokerage_connections') as b:b.add_column(sa.Column('sync_token_hash',sa.String(128),nullable=True));b.create_unique_constraint('uq_brokerage_connections_sync_token_hash',['sync_token_hash'])
 else: op.add_column('brokerage_connections',sa.Column('sync_token_hash',sa.String(128),nullable=True));op.create_unique_constraint('uq_brokerage_connections_sync_token_hash','brokerage_connections',['sync_token_hash'])
def downgrade():
 with op.batch_alter_table('brokerage_connections') as b:b.drop_constraint('uq_brokerage_connections_sync_token_hash',type_='unique');b.drop_column('sync_token_hash')
