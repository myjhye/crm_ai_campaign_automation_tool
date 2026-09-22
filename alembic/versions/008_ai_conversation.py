"""Group AI executions without storing conversation text."""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ai_execution_logs', sa.Column('conversation_id', sa.Uuid(), nullable=True))
    op.create_index('ix_ai_execution_logs_conversation_id', 'ai_execution_logs', ['conversation_id'])


def downgrade():
    op.drop_index('ix_ai_execution_logs_conversation_id', table_name='ai_execution_logs')
    op.drop_column('ai_execution_logs', 'conversation_id')
