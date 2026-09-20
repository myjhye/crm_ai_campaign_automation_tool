"""Persistent validated copy cache."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='005b'
down_revision='005a'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('ai_copy_cache',
        sa.Column('cache_key',sa.String(64),primary_key=True),
        sa.Column('dataset_id',sa.Uuid(),sa.ForeignKey('datasets.id',ondelete='CASCADE'),nullable=False),
        sa.Column('generated',postgresql.JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_ai_copy_cache_dataset_id','ai_copy_cache',['dataset_id'])


def downgrade():
    op.drop_table('ai_copy_cache')
