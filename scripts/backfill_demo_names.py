"""Backfill only legacy generated customer names in a verified demo dataset."""
import argparse
from uuid import UUID, NAMESPACE_URL, uuid5
from sqlalchemy import select
from app.core.config import Settings
from app.core.time import as_utc
from app.db.session import Database
from app.models.customers import Customer
from app.models.jobs import DatasetVersion
from app.services.datasets import require_dataset
from app.services.imports import data_version
from app.services.audit import record_change
from scripts.seed_demo import GROUPS, GENERATOR_VERSION
from scripts.data.korean_names import synthetic_name


def backfill(session, dataset_id, seed=42, size='small', dataset_key='default', apply=False):
    dataset = require_dataset(session, dataset_id, lock=True)
    if dataset.source != 'DEMO' or dataset.reference_at is None:
        raise ValueError('A generated demo dataset is required')
    identity = f'growthpilot:{GENERATOR_VERSION}:{seed}:{as_utc(dataset.reference_at).isoformat()}:{size}:{dataset_key}'
    if uuid5(NAMESPACE_URL, identity) != dataset.id:
        raise ValueError('Seed options do not match this dataset identity')
    changed = 0
    for row in session.scalars(select(Customer).where(Customer.dataset_id == dataset_id).with_for_update()):
        prefix, separator, number = row.external_id.rpartition('-')
        if prefix != 'customer' or not separator or not number.isdigit():
            continue
        legacy = f'{GROUPS[int(number) % len(GROUPS)]}-{int(number)}'
        if row.name not in (None, '', row.external_id, legacy):
            continue
        changed += 1
        if apply:
            row.name = synthetic_name(row.external_id, seed)
    if apply and changed:
        previous = data_version(session, dataset_id)
        session.add(DatasetVersion(dataset_id=dataset_id, version=previous + 1, reason='synthetic_names'))
        record_change(session, dataset_id=dataset_id, resource_id=dataset_id, actor_type='SYSTEM', action='DEMO_NAMES_UPDATED', request_id=None, previous_version=previous or None, new_version=previous + 1)
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset-id', type=UUID, required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--size', choices=['small', 'demo'], default='small')
    parser.add_argument('--dataset-key', default='default')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    db = Database(Settings().database_url.get_secret_value())
    try:
        with db.sessions.begin() as session:
            print(f'changed={backfill(session, **vars(args))} applied={args.apply}')
    finally:
        db.dispose()


if __name__ == '__main__':
    main()
