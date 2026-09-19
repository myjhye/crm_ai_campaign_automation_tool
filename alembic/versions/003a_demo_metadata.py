"""Public dataset metadata and versioned audit history."""
from alembic import op
import sqlalchemy as sa

revision = "003a"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("datasets", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("datasets", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.execute("UPDATE datasets SET updated_at = created_at")
    op.create_check_constraint(op.f("ck_datasets_version"), "datasets", "version > 0")
    op.add_column("audit_logs", sa.Column("previous_version", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("new_version", sa.Integer(), nullable=True))
    op.create_check_constraint(op.f("ck_audit_logs_previous_version"), "audit_logs", "previous_version IS NULL OR previous_version > 0")
    op.create_check_constraint(op.f("ck_audit_logs_new_version"), "audit_logs", "new_version IS NULL OR new_version > 0")
    op.create_index("ix_audit_dataset_created", "audit_logs", ["dataset_id", "created_at", "id"])


def downgrade():
    op.drop_index("ix_audit_dataset_created", table_name="audit_logs")
    op.drop_constraint(op.f("ck_audit_logs_new_version"), "audit_logs", type_="check")
    op.drop_constraint(op.f("ck_audit_logs_previous_version"), "audit_logs", type_="check")
    op.drop_column("audit_logs", "new_version")
    op.drop_column("audit_logs", "previous_version")
    op.drop_constraint(op.f("ck_datasets_version"), "datasets", type_="check")
    op.drop_column("datasets", "updated_at")
    op.drop_column("datasets", "version")
