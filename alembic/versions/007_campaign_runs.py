"""campaign simulation runs, assignments, and events"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='007'
down_revision='006a'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('orders',sa.Column('source',sa.String(20),server_default='UPLOADED',nullable=False))
    op.create_check_constraint(op.f('ck_orders_source'),'orders',"source IN ('UPLOADED','SIMULATED')")
    op.create_table('campaign_runs',
        sa.Column('dataset_id',sa.Uuid(),nullable=False),sa.Column('campaign_id',sa.Uuid(),nullable=False),
        sa.Column('approval_id',sa.Uuid(),nullable=False),sa.Column('validation_run_id',sa.Uuid(),nullable=False),
        sa.Column('job_id',sa.Uuid(),nullable=False),sa.Column('idempotency_key',sa.String(200),nullable=False),
        sa.Column('payload_hash',sa.String(64),nullable=False),sa.Column('status',sa.String(20),server_default='PENDING',nullable=False),
        sa.Column('seed',sa.String(64),nullable=False),sa.Column('response_rates',postgresql.JSONB(),server_default='{}',nullable=False),
        sa.Column('initial_count',sa.Integer(),nullable=False),sa.Column('reserved_count',sa.Integer(),nullable=False),
        sa.Column('excluded_count',sa.Integer(),nullable=False),sa.Column('sent_count',sa.Integer(),server_default='0',nullable=False),
        sa.Column('failed_count',sa.Integer(),server_default='0',nullable=False),sa.Column('started_at',sa.DateTime(timezone=True)),
        sa.Column('finished_at',sa.DateTime(timezone=True)),sa.Column('id',sa.Uuid(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.CheckConstraint("status IN ('PENDING','RUNNING','COMPLETED','FAILED')",name=op.f('ck_campaign_runs_status')),
        sa.CheckConstraint('initial_count >= 0 AND reserved_count >= 0 AND excluded_count >= 0 AND initial_count = reserved_count + excluded_count AND sent_count >= 0 AND failed_count >= 0',name=op.f('ck_campaign_runs_counts')),
        sa.ForeignKeyConstraint(['dataset_id'],['datasets.id'],name=op.f('fk_campaign_runs_dataset_id_datasets')),
        sa.ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id'],name=op.f('fk_campaign_runs_dataset_id_campaigns')),
        sa.ForeignKeyConstraint(['dataset_id','validation_run_id'],['validation_runs.dataset_id','validation_runs.id'],name=op.f('fk_campaign_runs_dataset_id_validation_runs')),
        sa.ForeignKeyConstraint(['dataset_id','job_id'],['jobs.dataset_id','jobs.id'],name=op.f('fk_campaign_runs_dataset_id_jobs')),
        sa.ForeignKeyConstraint(['approval_id'],['approvals.id'],name=op.f('fk_campaign_runs_approval_id_approvals')),
        sa.PrimaryKeyConstraint('id',name=op.f('pk_campaign_runs')),
        sa.UniqueConstraint('dataset_id','id',name='uq_campaign_run_dataset'),
        sa.UniqueConstraint('campaign_id','idempotency_key',name='uq_campaign_run_idempotency'))
    op.add_column('campaign_deliveries',sa.Column('run_id',sa.Uuid(),nullable=True))
    op.add_column('campaign_deliveries',sa.Column('variant_id',sa.Uuid(),nullable=True))
    op.add_column('campaign_deliveries',sa.Column('exclusion_reason',sa.String(50),nullable=True))
    op.drop_constraint(op.f('ck_campaign_deliveries_status'),'campaign_deliveries',type_='check')
    op.create_check_constraint(op.f('ck_campaign_deliveries_status'),'campaign_deliveries',"status IN ('RESERVED','SENT','FAILED','EXCLUDED')")
    op.create_foreign_key(op.f('fk_campaign_deliveries_dataset_id_campaign_runs'),'campaign_deliveries','campaign_runs',['dataset_id','run_id'],['dataset_id','id'])
    op.create_foreign_key(op.f('fk_campaign_deliveries_variant_id_campaign_variants'),'campaign_deliveries','campaign_variants',['variant_id'],['id'])
    op.create_unique_constraint('uq_campaign_run_customer','campaign_deliveries',['run_id','customer_id'])
    op.create_table('campaign_events',
        sa.Column('dataset_id',sa.Uuid(),nullable=False),sa.Column('campaign_id',sa.Uuid(),nullable=False),
        sa.Column('run_id',sa.Uuid(),nullable=False),sa.Column('delivery_id',sa.Uuid(),nullable=False),
        sa.Column('customer_id',sa.Uuid(),nullable=False),sa.Column('variant_id',sa.Uuid(),nullable=False),
        sa.Column('order_id',sa.Uuid(),nullable=True),
        sa.Column('external_id',sa.String(200),nullable=False),sa.Column('event_type',sa.String(30),nullable=False),
        sa.Column('event_at',sa.DateTime(timezone=True),nullable=False),sa.Column('source',sa.String(20),server_default='SIMULATED',nullable=False),
        sa.Column('id',sa.Uuid(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('now()'),nullable=False),
        sa.CheckConstraint("event_type IN ('DELIVERED','OPEN','CLICK','CONVERSION','UNSUBSCRIBE')",name=op.f('ck_campaign_events_event_type')),
        sa.CheckConstraint("source IN ('UPLOADED','SIMULATED')",name=op.f('ck_campaign_events_source')),
        sa.ForeignKeyConstraint(['dataset_id'],['datasets.id'],name=op.f('fk_campaign_events_dataset_id_datasets')),
        sa.ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id'],name=op.f('fk_campaign_events_dataset_id_campaigns')),
        sa.ForeignKeyConstraint(['dataset_id','run_id'],['campaign_runs.dataset_id','campaign_runs.id'],name=op.f('fk_campaign_events_dataset_id_campaign_runs')),
        sa.ForeignKeyConstraint(['dataset_id','customer_id'],['customers.dataset_id','customers.id'],name=op.f('fk_campaign_events_dataset_id_customers')),
        sa.ForeignKeyConstraint(['dataset_id','customer_id','order_id'],['orders.dataset_id','orders.customer_id','orders.id'],name=op.f('fk_campaign_events_dataset_id_orders')),
        sa.ForeignKeyConstraint(['delivery_id'],['campaign_deliveries.id'],name=op.f('fk_campaign_events_delivery_id_campaign_deliveries')),
        sa.ForeignKeyConstraint(['variant_id'],['campaign_variants.id'],name=op.f('fk_campaign_events_variant_id_campaign_variants')),
        sa.PrimaryKeyConstraint('id',name=op.f('pk_campaign_events')),
        sa.UniqueConstraint('dataset_id','external_id',name='uq_campaign_event_external'))
    op.create_index('ix_campaign_events_campaign_time','campaign_events',['campaign_id','event_at'])

def downgrade():
    op.drop_index('ix_campaign_events_campaign_time',table_name='campaign_events'); op.drop_table('campaign_events')
    op.drop_constraint('uq_campaign_run_customer','campaign_deliveries',type_='unique')
    op.drop_constraint(op.f('fk_campaign_deliveries_variant_id_campaign_variants'),'campaign_deliveries',type_='foreignkey')
    op.drop_constraint(op.f('fk_campaign_deliveries_dataset_id_campaign_runs'),'campaign_deliveries',type_='foreignkey')
    op.drop_constraint(op.f('ck_campaign_deliveries_status'),'campaign_deliveries',type_='check')
    op.create_check_constraint(op.f('ck_campaign_deliveries_status'),'campaign_deliveries',"status IN ('SENT','FAILED','EXCLUDED')")
    op.drop_column('campaign_deliveries','exclusion_reason'); op.drop_column('campaign_deliveries','variant_id'); op.drop_column('campaign_deliveries','run_id')
    op.drop_table('campaign_runs')
    op.drop_constraint(op.f('ck_orders_source'),'orders',type_='check'); op.drop_column('orders','source')
