"""Translate the exact legacy default demo names, preserving edited names."""
from alembic import op
import sqlalchemy as sa

revision = "003d"
down_revision = "003c"
branch_labels = None
depends_on = None


def upgrade():
    for before, after in (("Demo small / seed 42", "체험용 소형 샘플"), ("Demo demo / seed 42", "체험용 전체 샘플")):
        op.get_bind().execute(sa.text("UPDATE datasets SET name=:after, version=version+1, updated_at=now() WHERE name=:before AND source='DEMO' AND purpose='ANALYSIS' AND version=1"), {"before": before, "after": after})


def downgrade():
    # Display names are user data; do not undo subsequent visitor edits.
    pass
