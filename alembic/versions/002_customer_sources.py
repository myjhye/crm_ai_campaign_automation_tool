"""customer_sources schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('customers',
    sa.Column('external_id', sa.String(length=200), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=True),
    sa.Column('signup_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False),
    sa.Column('last_purchase_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('total_purchase_amount', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
    sa.Column('order_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('ACTIVE','DORMANT','CHURN_RISK','WITHDRAWN')", name=op.f('ck_customers_status')),
    sa.CheckConstraint('last_purchase_at IS NULL OR last_purchase_at >= signup_at', name=op.f('ck_customers_purchase_time')),
    sa.CheckConstraint('total_purchase_amount >= 0 AND order_count >= 0', name=op.f('ck_customers_purchase_totals')),
    sa.CheckConstraint('withdrawn_at IS NULL OR withdrawn_at >= signup_at', name=op.f('ck_customers_withdrawal_time')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_customers_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_customers')),
    sa.UniqueConstraint('dataset_id', 'external_id', name='uq_customer_external'),
    sa.UniqueConstraint('dataset_id', 'id', name='uq_customer_dataset_id')
    )
    op.create_table('products',
    sa.Column('external_id', sa.String(length=200), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_products_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_products')),
    sa.UniqueConstraint('dataset_id', 'external_id', name='uq_product_external'),
    sa.UniqueConstraint('dataset_id', 'id', name='uq_product_dataset_id')
    )
    op.create_table('customer_channels',
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('channel', sa.String(length=10), nullable=False),
    sa.Column('consent', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('consent_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('contact', sa.String(length=1000), nullable=True),
    sa.Column('is_valid', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('hard_bounce', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("channel IN ('EMAIL','PUSH','SMS')", name=op.f('ck_customer_channels_channel')),
    sa.ForeignKeyConstraint(['dataset_id', 'customer_id'], ['customers.dataset_id', 'customers.id'], name=op.f('fk_customer_channels_dataset_id_customers')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_customer_channels_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_customer_channels')),
    sa.UniqueConstraint('dataset_id', 'customer_id', 'channel', name='uq_customer_channel')
    )
    op.create_table('orders',
    sa.Column('external_id', sa.String(length=200), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('COMPLETED','CANCELLED','REFUNDED')", name=op.f('ck_orders_status')),
    sa.CheckConstraint('amount >= 0', name=op.f('ck_orders_amount')),
    sa.ForeignKeyConstraint(['dataset_id', 'customer_id'], ['customers.dataset_id', 'customers.id'], name=op.f('fk_orders_dataset_id_customers')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_orders_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_orders')),
    sa.UniqueConstraint('dataset_id', 'customer_id', 'id', name='uq_order_customer_id'),
    sa.UniqueConstraint('dataset_id', 'external_id', name='uq_order_external'),
    sa.UniqueConstraint('dataset_id', 'id', name='uq_order_dataset_id')
    )
    op.create_index('ix_orders_customer_purchased', 'orders', ['customer_id', 'purchased_at'], unique=False)
    op.create_table('customer_events',
    sa.Column('external_id', sa.String(length=200), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=True),
    sa.Column('event_type', sa.String(length=30), nullable=False),
    sa.Column('event_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("event_type != 'PURCHASE' OR order_id IS NOT NULL", name=op.f('ck_customer_events_purchase_order')),
    sa.CheckConstraint("event_type IN ('VIEW','CART','PURCHASE','EMAIL_OPEN','CLICK','LANDING_VIEW','UNSUBSCRIBE')", name=op.f('ck_customer_events_event_type')),
    sa.ForeignKeyConstraint(['dataset_id', 'customer_id', 'order_id'], ['orders.dataset_id', 'orders.customer_id', 'orders.id'], name=op.f('fk_customer_events_dataset_id_orders')),
    sa.ForeignKeyConstraint(['dataset_id', 'customer_id'], ['customers.dataset_id', 'customers.id'], name=op.f('fk_customer_events_dataset_id_customers')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_customer_events_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_customer_events')),
    sa.UniqueConstraint('dataset_id', 'external_id', name='uq_customer_event_external')
    )
    op.create_index('ix_customer_events_customer_time', 'customer_events', ['customer_id', 'event_at'], unique=False)
    op.create_table('order_items',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('line_id', sa.String(length=100), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('quantity > 0 AND amount >= 0', name=op.f('ck_order_items_amount_quantity')),
    sa.ForeignKeyConstraint(['dataset_id', 'order_id'], ['orders.dataset_id', 'orders.id'], name=op.f('fk_order_items_dataset_id_orders')),
    sa.ForeignKeyConstraint(['dataset_id', 'product_id'], ['products.dataset_id', 'products.id'], name=op.f('fk_order_items_dataset_id_products')),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_order_items_dataset_id_datasets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_order_items')),
    sa.UniqueConstraint('dataset_id', 'order_id', 'line_id', name='uq_order_line')
    )


def downgrade():
    op.drop_table('order_items')
    op.drop_index('ix_customer_events_customer_time', table_name='customer_events')
    op.drop_table('customer_events')
    op.drop_index('ix_orders_customer_purchased', table_name='orders')
    op.drop_table('orders')
    op.drop_table('customer_channels')
    op.drop_table('products')
    op.drop_table('customers')
