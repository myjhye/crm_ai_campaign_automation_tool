"""soft archive campaigns"""
from alembic import op
import sqlalchemy as sa

revision='006a'
down_revision='006'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('campaigns',sa.Column('archived_at',sa.DateTime(timezone=True),nullable=True))
    op.create_index('ix_campaigns_dataset_archived','campaigns',['dataset_id','archived_at'])

def downgrade():
    op.drop_index('ix_campaigns_dataset_archived',table_name='campaigns')
    op.drop_column('campaigns','archived_at')
