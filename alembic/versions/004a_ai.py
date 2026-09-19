"""AI proposals and privacy-preserving execution records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '004a'
down_revision = '004'
branch_labels = depends_on = None


def identity():
    return [sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table('ai_action_proposals', *identity(),
        sa.Column('dataset_id', sa.Uuid(), sa.ForeignKey('datasets.id'), nullable=False),
        sa.Column('payload', JSONB(), nullable=False), sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True)), sa.Column('segment_id', sa.Uuid()),
        sa.ForeignKeyConstraint(['dataset_id', 'segment_id'], ['segments.dataset_id', 'segments.id']))
    op.create_table('ai_execution_logs', *identity(),
        sa.Column('dataset_id', sa.Uuid(), sa.ForeignKey('datasets.id'), nullable=False),
        sa.Column('request_id', sa.Uuid(), nullable=False), sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('provider', sa.String(20), nullable=False), sa.Column('model', sa.String(100), nullable=False),
        sa.Column('prompt_version', sa.String(20), nullable=False), sa.Column('status', sa.String(30), nullable=False),
        sa.Column('tool_name', sa.String(50)), sa.Column('elapsed_ms', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False))


def downgrade():
    op.drop_table('ai_execution_logs')
    op.drop_table('ai_action_proposals')
