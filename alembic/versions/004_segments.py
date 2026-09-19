"""Versioned segment conditions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '004'
down_revision = '003d'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('segments', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('dataset_id', sa.Uuid(), sa.ForeignKey('datasets.id'), nullable=False), sa.Column('name', sa.String(200), nullable=False), sa.Column('version', sa.Integer(), nullable=False, server_default='1'), sa.Column('archived_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('dataset_id', 'id', name='uq_segment_dataset_id'), sa.CheckConstraint('version > 0', name=op.f('ck_segments_version')))
    op.create_table('segment_revisions', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('dataset_id', sa.Uuid(), sa.ForeignKey('datasets.id'), nullable=False), sa.Column('segment_id', sa.Uuid(), nullable=False), sa.Column('version', sa.Integer(), nullable=False), sa.Column('name', sa.String(200), nullable=False),
        sa.Column('condition_json', JSONB(), nullable=False), sa.Column('reference_at', sa.DateTime(timezone=True), nullable=False), sa.Column('data_version', sa.Integer(), nullable=False), sa.Column('condition_hash', sa.String(64), nullable=False), sa.Column('created_source', sa.String(20), nullable=False, server_default='VISITOR'),
        sa.ForeignKeyConstraint(['dataset_id','segment_id'], ['segments.dataset_id','segments.id']), sa.UniqueConstraint('segment_id','version',name='uq_segment_revision'), sa.UniqueConstraint('dataset_id','id',name='uq_segment_revision_dataset'),
        sa.CheckConstraint('version > 0 AND data_version >= 0',name=op.f('ck_segment_revisions_versions')), sa.CheckConstraint("created_source IN ('VISITOR','AI','SYSTEM')",name=op.f('ck_segment_revisions_source')))

def downgrade():
    op.drop_table('segment_revisions')
    op.drop_table('segments')
