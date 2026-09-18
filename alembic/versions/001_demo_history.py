"""demo_history schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('datasets',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('source', sa.String(length=20), server_default='DEMO', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('DEMO','UPLOADED','SIMULATED')", name=op.f('ck_datasets_source')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_datasets'))
    )
    op.create_table('audit_logs',
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.Column('actor_type', sa.String(length=20), nullable=False),
    sa.Column('resource_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('request_id', sa.Uuid(), nullable=True),
    sa.Column('event_key', sa.String(length=200), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("actor_type IN ('VISITOR','AI','SYSTEM')", name=op.f('ck_audit_logs_actor_type')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_audit_logs_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs')),
    sa.UniqueConstraint('dataset_id', 'event_key', name='uq_audit_event_key')
    )


def downgrade():
    op.drop_table('audit_logs')
    op.drop_table('datasets')
