"""Deterministic synthetic source data; never delete or replace a dataset."""
import argparse
import hashlib
from scripts.data.korean_names import synthetic_name
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text

from app.core.config import Settings
from app.core.time import as_utc
from app.db.session import Database
from app.models.datasets import Dataset
from app.models.customers import Customer, CustomerChannel
from app.models.jobs import DatasetVersion
from app.schemas.imports import SCHEMAS
from app.services.audit import record_change
from app.services.imports import plan_merge, apply_merge

GENERATOR_VERSION = "v2"
GROUPS = ["dormant_vip", "cart_abandon", "no_consent", "withdrawn", "hard_bounce",
          "missing_contact", "mobile_drop", "recent", "no_purchase", "repeat"]
SIZE_CONFIG = {
    "small": {"customers": 300, "products": 10, "name": "체험용 확장 샘플 (고객 300명)"},
    "medium": {"customers": 5_000, "products": 300, "name": "체험용 중형 샘플 (고객 5,000명)"},
    "demo": {"customers": 10_000, "products": 300, "name": "체험용 전체 샘플"},
}


def source_rows(seed, reference_at, size):
    config = SIZE_CONFIG[size]
    count = config["customers"]
    product_count = config["products"]
    offset = int(hashlib.sha256(str(seed).encode()).hexdigest()[:8], 16)
    customers = []
    for i in range(count):
        group = i % 10
        customers.append(dict(external_id=f"customer-{i}", name=synthetic_name(f"customer-{i}", seed),
            signup_at=reference_at - timedelta(days=365),
            status="WITHDRAWN" if group == 3 else "ACTIVE", email_consent=group != 2,
            withdrawn_at=reference_at - timedelta(days=2) if group == 3 else None,
            email=f"demo-{i}@example.invalid" if group != 5 else None,
            email_valid=group != 5, hard_bounce=group == 4,
            consent_changed_at=reference_at - timedelta(days=365)))
    yield "customers", customers
    products = [dict(external_id=f"product-{i}", name=f"Synthetic product {i}",
                     category=["fashion", "home", "sports"][i % 3]) for i in range(product_count)]
    yield "products", products
    buyers = [i for i in range(count) if i % 10 not in (1, 6, 8)]
    orders = []
    for i in range(count * 3):
        customer = buyers[(i + offset) % len(buyers)]
        days = 75 + i % 10 if customer % 10 == 0 else 3 + i % 25
        orders.append(dict(external_id=f"order-{i}", customer_external_id=f"customer-{customer}",
            purchased_at=reference_at - timedelta(days=days, seconds=i % 3600),
            status="COMPLETED", amount=Decimal("150000") if customer % 10 == 0 else Decimal(10000 + (i + offset) % 20 * 1000)))
    yield "orders", orders
    yield "order_items", [dict(order_external_id=row["external_id"], line_id="1",
        product_external_id=f"product-{(i + offset) % product_count}", quantity=1, amount=row["amount"])
        for i, row in enumerate(orders)]
    events = [dict(external_id=f"purchase-{i}", customer_external_id=row["customer_external_id"],
        event_type="PURCHASE", event_at=row["purchased_at"], order_external_id=row["external_id"],
        properties={"device_type": "desktop"}) for i, row in enumerate(orders)]
    for i in range(count * 17):
        customer = i % count
        group = customer % 10
        event_type = "CART" if group == 1 else ("LANDING_VIEW" if group == 6 else "VIEW")
        events.append(dict(external_id=f"behavior-{i}", customer_external_id=f"customer-{customer}",
            event_type=event_type, event_at=reference_at - timedelta(days=3 + (i // count) % 20, seconds=i % 3600),
            properties={"device_type": "mobile" if group == 6 else "desktop", "page": "/landing" if group == 6 else "/products"}))
    yield "events", events


def seed_demo(session, *, seed, reference_at, size="small", dataset_key="default"):
    reference_at = as_utc(reference_at)
    if size not in SIZE_CONFIG:
        raise ValueError("Unsupported size")
    identity = f"growthpilot:{GENERATOR_VERSION}:{seed}:{reference_at.isoformat()}:{size}:{dataset_key}"
    dataset_id = uuid5(NAMESPACE_URL, identity)
    # Serialize first creation before the dataset row exists.
    lock_key = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    existing = session.get(Dataset, dataset_id)
    if existing:
        return existing, False
    name = SIZE_CONFIG[size]["name"]
    dataset = Dataset(id=dataset_id, name=name, source="DEMO", reference_at=reference_at)
    session.add(dataset)
    session.flush()
    for kind, sources in source_rows(seed, reference_at, size):
        rows = [(i + 2, SCHEMAS[kind].model_validate(row).model_dump()) for i, row in enumerate(sources)]
        if kind == "events":
            for _, row in rows:
                row["properties"] = {k: v for k, v in row["properties"].items() if v is not None}
        mutations, summary = plan_merge(session, dataset.id, kind, rows, "insert", reference_at)
        if summary["error_count"]:
            raise ValueError(f"Invalid generated {kind}: {summary['errors']}")
        apply_merge(session, dataset.id, kind, mutations, reference_at)
    # CSV customer import creates EMAIL. Add deterministic PUSH/SMS states so every
    # channel can demonstrate eligible, opt-out, missing and invalid recipients.
    customers = session.scalars(select(Customer).where(Customer.dataset_id == dataset.id).order_by(Customer.external_id)).all()
    channel_rows = {(row.customer_id, row.channel): row for row in session.scalars(
        select(CustomerChannel).where(CustomerChannel.dataset_id == dataset.id, CustomerChannel.channel.in_(("PUSH", "SMS"))))}
    for customer in customers:
        number = int(customer.external_id.rsplit("-", 1)[-1])
        group = number % 10
        values = {
            "PUSH": dict(consent=group not in (2, 8), contact=None if group == 5 else f"push-token-{number}",
                         is_valid=group not in (4, 5), hard_bounce=group == 4),
            "SMS": dict(consent=group not in (2, 6), contact=None if group == 5 else f"0100000{number:04d}",
                        is_valid=group not in (4, 5), hard_bounce=False),
        }
        for channel, state in values.items():
            row = channel_rows.get((customer.id, channel))
            if row is None:
                row = CustomerChannel(dataset_id=dataset.id, customer_id=customer.id, channel=channel)
                session.add(row)
            for key, value in state.items(): setattr(row, key, value)
            row.consent_changed_at = reference_at - timedelta(days=365)
    session.add(DatasetVersion(dataset_id=dataset.id, version=1, reason=f"seed:{GENERATOR_VERSION}"))
    record_change(session, dataset_id=dataset.id, resource_id=dataset.id, actor_type="SYSTEM",
                  action="DEMO_SEEDED", request_id=None, previous_version=None, new_version=1)
    return dataset, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reference-at", default="2026-09-20T00:00:00Z", help="ISO 8601 timestamp with timezone")
    parser.add_argument("--size", choices=list(SIZE_CONFIG), default="small")
    parser.add_argument("--dataset-key", default="default", help="Change this to create a fresh demo copy")
    args = parser.parse_args()
    try:
        reference_at = as_utc(datetime.fromisoformat(args.reference_at))
    except ValueError:
        parser.error("reference-at must be a timezone-aware ISO 8601 timestamp")
    settings = Settings()
    if not settings.database_url:
        parser.error("DATABASE_URL required")
    db = Database(settings.database_url.get_secret_value())
    try:
        with db.sessions.begin() as session:
            dataset, created = seed_demo(session, seed=args.seed, reference_at=reference_at,
                                         size=args.size, dataset_key=args.dataset_key)
            print(f"dataset_id={dataset.id} created={created}")
    finally:
        db.dispose()

if __name__ == "__main__":
    main()
