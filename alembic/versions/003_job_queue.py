"""job_queue schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('dataset_versions',
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=200), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('version > 0', name=op.f('ck_dataset_versions_version')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_dataset_versions_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_dataset_versions')),
    sa.UniqueConstraint('dataset_id', 'version', name='uq_dataset_version')
    )
    op.create_table('jobs',
    sa.Column('kind', sa.String(length=100), nullable=False),
    sa.Column('idempotency_key', sa.String(length=200), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
    sa.Column('attempt', sa.Integer(), server_default='0', nullable=False),
    sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lease_token', sa.Uuid(), nullable=True),
    sa.Column('progress', sa.Integer(), server_default='0', nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error_code', sa.String(length=100), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("(status = 'RUNNING' AND lease_token IS NOT NULL AND lease_until IS NOT NULL AND heartbeat_at IS NOT NULL) OR (status != 'RUNNING' AND lease_token IS NULL AND lease_until IS NULL)", name=op.f('ck_jobs_lease')),
    sa.CheckConstraint("status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')", name=op.f('ck_jobs_status')),
    sa.CheckConstraint('attempt >= 0 AND max_attempts > 0 AND attempt <= max_attempts', name=op.f('ck_jobs_attempts')),
    sa.CheckConstraint('progress BETWEEN 0 AND 100', name=op.f('ck_jobs_progress')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_jobs_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs')),
    sa.UniqueConstraint('dataset_id', 'id', name='uq_job_dataset_id'),
    sa.UniqueConstraint('dataset_id', 'kind', 'idempotency_key', name='uq_job_idempotency')
    )
    op.create_index('ix_jobs_available', 'jobs', ['status', 'available_at'], unique=False)
    op.create_index('ix_jobs_lease', 'jobs', ['status', 'lease_until'], unique=False)
    op.create_table('import_batches',
    sa.Column('kind', sa.String(length=50), nullable=False),
    sa.Column('file_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='PREVIEW', nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=True),
    sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('PREVIEW','INVALID','QUEUED','COMPLETED','FAILED')", name=op.f('ck_import_batches_status')),
    sa.ForeignKeyConstraint(['dataset_id', 'job_id'], ['jobs.dataset_id', 'jobs.id'], name=op.f('fk_import_batches_dataset_id_jobs')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_import_batches_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_batches'))
    )


def downgrade():
    op.drop_table('import_batches')
    op.drop_index('ix_jobs_lease', table_name='jobs')
    op.drop_index('ix_jobs_available', table_name='jobs')
    op.drop_table('jobs')
    op.drop_table('dataset_versions')
