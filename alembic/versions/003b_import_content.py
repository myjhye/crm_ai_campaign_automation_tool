"""Immutable staged CSV content and retention."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "003b"
down_revision = "003a"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("datasets", sa.Column("reference_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("import_batches", sa.Column("content", sa.LargeBinary(), nullable=True))
    op.add_column("import_batches", sa.Column("options", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("import_batches", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column("datasets", "reference_at")
    op.drop_column("import_batches", "expires_at")
    op.drop_column("import_batches", "options")
    op.drop_column("import_batches", "content")
