"""policy validation and approvals"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '006'
down_revision = '005b'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('policy_settings',
        sa.Column('dataset_id',sa.Uuid(),nullable=False),sa.Column('version',sa.Integer(),server_default='1',nullable=False),
        sa.Column('daily_limit',sa.Integer(),server_default='1',nullable=False),sa.Column('weekly_limit',sa.Integer(),server_default='3',nullable=False),
        sa.Column('forbidden_phrases',postgresql.JSONB(),server_default='{}',nullable=False),sa.Column('required_phrases',postgresql.JSONB(),server_default='{}',nullable=False),
        sa.Column('id',sa.Uuid(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.CheckConstraint('version > 0 AND daily_limit > 0 AND weekly_limit > 0',name=op.f('ck_policy_settings_values')),
        sa.ForeignKeyConstraint(['dataset_id'],['datasets.id'],name=op.f('fk_policy_settings_dataset_id_datasets')),sa.PrimaryKeyConstraint('id',name=op.f('pk_policy_settings')),sa.UniqueConstraint('dataset_id'))
    op.create_table('campaign_deliveries',
        sa.Column('dataset_id',sa.Uuid(),nullable=False),sa.Column('campaign_id',sa.Uuid(),nullable=False),sa.Column('customer_id',sa.Uuid(),nullable=False),
        sa.Column('channel',sa.String(10),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('sent_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('id',sa.Uuid(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.CheckConstraint("channel IN ('EMAIL','PUSH','SMS')",name=op.f('ck_campaign_deliveries_channel')),sa.CheckConstraint("status IN ('SENT','FAILED','EXCLUDED')",name=op.f('ck_campaign_deliveries_status')),
        sa.ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id'],name=op.f('fk_campaign_deliveries_dataset_id_campaigns')),
        sa.ForeignKeyConstraint(['dataset_id','customer_id'],['customers.dataset_id','customers.id'],name=op.f('fk_campaign_deliveries_dataset_id_customers')),
        sa.ForeignKeyConstraint(['dataset_id'],['datasets.id'],name=op.f('fk_campaign_deliveries_dataset_id_datasets')),sa.PrimaryKeyConstraint('id',name=op.f('pk_campaign_deliveries')),
        sa.UniqueConstraint('campaign_id','customer_id',name='uq_campaign_delivery_customer'))
    op.create_index('ix_campaign_deliveries_customer_sent','campaign_deliveries',['dataset_id','customer_id','channel','sent_at'])
    op.create_table('validation_runs',
        sa.Column('dataset_id',sa.Uuid(),nullable=False),sa.Column('campaign_id',sa.Uuid(),nullable=False),sa.Column('campaign_version',sa.Integer(),nullable=False),
        sa.Column('segment_revision_id',sa.Uuid(),nullable=False),sa.Column('policy_version',sa.Integer(),nullable=False),sa.Column('data_version',sa.Integer(),nullable=False),
        sa.Column('reference_at',sa.DateTime(timezone=True),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('initial_count',sa.Integer(),nullable=False),sa.Column('eligible_count',sa.Integer(),nullable=False),sa.Column('excluded_count',sa.Integer(),nullable=False),
        sa.Column('passed',sa.Boolean(),nullable=False),sa.Column('rules',postgresql.JSONB(),server_default='[]',nullable=False),sa.Column('blockers',postgresql.JSONB(),server_default='[]',nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('id',sa.Uuid(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.CheckConstraint('campaign_version > 0 AND policy_version > 0 AND data_version >= 0',name=op.f('ck_validation_runs_versions')),
        sa.CheckConstraint('initial_count >= 0 AND eligible_count >= 0 AND excluded_count >= 0 AND initial_count = eligible_count + excluded_count',name=op.f('ck_validation_runs_counts')),
        sa.ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id'],name=op.f('fk_validation_runs_dataset_id_campaigns')),
        sa.ForeignKeyConstraint(['dataset_id','segment_revision_id'],['segment_revisions.dataset_id','segment_revisions.id'],name=op.f('fk_validation_runs_dataset_id_segment_revisions')),
        sa.ForeignKeyConstraint(['dataset_id'],['datasets.id'],name=op.f('fk_validation_runs_dataset_id_datasets')),sa.PrimaryKeyConstraint('id',name=op.f('pk_validation_runs')),sa.UniqueConstraint('dataset_id','id',name='uq_validation_run_dataset'))
    op.create_table('validation_recipients',
        sa.Column('dataset_id',sa.Uuid(),nullable=False),sa.Column('validation_run_id',sa.Uuid(),nullable=False),sa.Column('customer_id',sa.Uuid(),nullable=False),
        sa.Column('eligible',sa.Boolean(),nullable=False),sa.Column('primary_reason',sa.String(50),nullable=True),sa.Column('reasons',postgresql.JSONB(),server_default='[]',nullable=False),
        sa.Column('id',sa.Uuid(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.ForeignKeyConstraint(['dataset_id','validation_run_id'],['validation_runs.dataset_id','validation_runs.id'],name=op.f('fk_validation_recipients_dataset_id_validation_runs')),
        sa.ForeignKeyConstraint(['dataset_id','customer_id'],['customers.dataset_id','customers.id'],name=op.f('fk_validation_recipients_dataset_id_customers')),
        sa.ForeignKeyConstraint(['dataset_id'],['datasets.id'],name=op.f('fk_validation_recipients_dataset_id_datasets')),sa.PrimaryKeyConstraint('id',name=op.f('pk_validation_recipients')),sa.UniqueConstraint('validation_run_id','customer_id',name='uq_validation_recipient'))
    op.create_table('approvals',
        sa.Column('dataset_id',sa.Uuid(),nullable=False),sa.Column('campaign_id',sa.Uuid(),nullable=False),sa.Column('validation_run_id',sa.Uuid(),nullable=False),
        sa.Column('campaign_version',sa.Integer(),nullable=False),sa.Column('status',sa.String(20),server_default='PENDING',nullable=False),
        sa.Column('decision_source',sa.String(20),nullable=True),sa.Column('comment',sa.String(1000),nullable=True),sa.Column('decided_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('id',sa.Uuid(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','WITHDRAWN')",name=op.f('ck_approvals_status')),sa.CheckConstraint("decision_source IS NULL OR decision_source IN ('VISITOR','AI','SYSTEM')",name=op.f('ck_approvals_decision_source')),
        sa.ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id'],name=op.f('fk_approvals_dataset_id_campaigns')),
        sa.ForeignKeyConstraint(['dataset_id','validation_run_id'],['validation_runs.dataset_id','validation_runs.id'],name=op.f('fk_approvals_dataset_id_validation_runs')),
        sa.ForeignKeyConstraint(['dataset_id'],['datasets.id'],name=op.f('fk_approvals_dataset_id_datasets')),sa.PrimaryKeyConstraint('id',name=op.f('pk_approvals')))
    op.create_index('ix_approvals_campaign_created','approvals',['campaign_id','created_at'])
    op.create_index('uq_approvals_pending_campaign','approvals',['campaign_id'],unique=True,postgresql_where=sa.text("status = 'PENDING'"))

def downgrade():
    op.drop_index('uq_approvals_pending_campaign',table_name='approvals'); op.drop_index('ix_approvals_campaign_created',table_name='approvals'); op.drop_table('approvals')
    op.drop_table('validation_recipients'); op.drop_table('validation_runs')
    op.drop_index('ix_campaign_deliveries_customer_sent',table_name='campaign_deliveries'); op.drop_table('campaign_deliveries'); op.drop_table('policy_settings')
