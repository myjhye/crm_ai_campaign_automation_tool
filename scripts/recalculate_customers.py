"""Compare cached metrics with source orders; persist only with --apply."""
import argparse
from uuid import UUID
from sqlalchemy import select
from app.core.config import Settings
from app.db.session import Database
from app.models.customers import Customer
from app.models.jobs import DatasetVersion
from app.services.datasets import require_dataset
from app.services.imports import recalculate, data_version
from app.services.audit import record_change


def check_metrics(session, dataset_id, apply=False):
    dataset = require_dataset(session, dataset_id, lock=True)
    if dataset.reference_at is None:
        raise ValueError("Dataset has no import reference_at")
    def snapshot():
        return {r.id: (r.order_count, r.total_purchase_amount, r.last_purchase_at, r.status)
                for r in session.scalars(select(Customer).where(Customer.dataset_id == dataset_id))}
    before = snapshot()
    # Savepoint makes the default check non-mutating even for callers that commit.
    with session.begin_nested() as savepoint:
        recalculate(session, dataset_id, dataset.reference_at)
        after = snapshot()
        changed = sum(before[key] != value for key, value in after.items())
        if not apply:
            savepoint.rollback()
    if apply and changed:
        previous = data_version(session, dataset_id)
        session.add(DatasetVersion(dataset_id=dataset_id, version=previous + 1, reason="metrics_recalculated"))
        record_change(session, dataset_id=dataset_id, resource_id=dataset_id, actor_type="SYSTEM",
                      action="METRICS_RECALCULATED", request_id=None, previous_version=previous or None,
                      new_version=previous + 1)
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", type=UUID, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not settings.database_url:
        parser.error("DATABASE_URL required")
    db = Database(settings.database_url.get_secret_value())
    try:
        with db.sessions.begin() as session:
            changed = check_metrics(session, args.dataset_id, args.apply)
            print(f"mismatched_customers={changed} applied={args.apply}")
    finally:
        db.dispose()

if __name__ == "__main__":
    main()
