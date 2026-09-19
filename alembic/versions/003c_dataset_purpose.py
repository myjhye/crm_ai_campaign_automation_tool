"""Separate public analysis datasets from internal diagnostics."""
from alembic import op
import sqlalchemy as sa

revision = "003c"
down_revision = "003b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("datasets", sa.Column("purpose", sa.String(20), nullable=False, server_default="ANALYSIS"))
    op.create_check_constraint(op.f("ck_datasets_purpose"), "datasets", "purpose IN ('ANALYSIS','SYSTEM')")
    op.execute("UPDATE datasets SET purpose = 'SYSTEM' WHERE name = 'Worker diagnostic'")


def downgrade():
    op.drop_constraint(op.f("ck_datasets_purpose"), "datasets", type_="check")
    op.drop_column("datasets", "purpose")
