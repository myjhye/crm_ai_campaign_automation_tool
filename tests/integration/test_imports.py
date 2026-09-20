from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, update

from app.core.config import Settings
from app.main import create_app
from app.models.customers import Customer, CustomerChannel, Order, CustomerEvent, Product
from app.models.datasets import Dataset, AuditLog
from app.models.jobs import ImportBatch, Job, DatasetVersion
from app.services import imports
from app.workers.runner import run_once
from scripts.cleanup_imports import cleanup
from scripts.seed_demo import seed_demo

pytestmark = pytest.mark.postgres
REFERENCE = datetime(2026, 9, 19, tzinfo=timezone.utc)
FIXTURES = Path("tests/fixtures/imports")
SETTINGS = Settings(_env_file=None, database_url=None)

@pytest.fixture
def client(database):
    app = create_app(SETTINGS)
    app.state.database = database
    with TestClient(app) as client:
        yield client

@pytest.fixture
def dataset_id(client):
    return client.post("/api/v1/datasets", json={"name": "Import fixture"}).json()["id"]


def preview(client, dataset_id, kind, content=None, mode="insert", reference=REFERENCE):
    content = (FIXTURES / f"{kind}.csv").read_bytes() if content is None else content
    response = client.post(f"/api/v1/data/import/{kind}/preview", content=content,
        headers={"Content-Type": "text/csv"}, params={"dataset_id": dataset_id,
        "reference_at": reference.isoformat(), "mode": mode})
    assert response.status_code == 201, response.text
    return response.json()


def execute(client, database, batch):
    response = client.post(f"/api/v1/data/import/{batch['import_batch_id']}/commit")
    assert response.status_code == 202, response.text
    assert run_once(database, SETTINGS)
    result = client.get(f"/api/v1/data/import/{batch['import_batch_id']}").json()
    assert result["status"] == "COMPLETED", result
    return result


def test_full_import_duplicate_and_derived_totals(client, database, dataset_id):
    for kind in ("customers", "products", "orders", "order_items", "events"):
        batch = preview(client, dataset_id, kind)
        assert batch["summary"]["error_count"] == 0
        assert batch["summary"]["created"] == 1
        result = execute(client, database, batch)
        repeated = client.post(f"/api/v1/data/import/{batch['import_batch_id']}/commit").json()
        assert repeated["job_id"] == result["job_id"]
        again = preview(client, dataset_id, kind)
        assert again["summary"]["duplicates"] == 1
        execute(client, database, again)
    with database.sessions() as session:
        customer = session.scalar(select(Customer))
        assert customer.total_purchase_amount == Decimal("300000.00")
        assert customer.order_count == 1 and customer.status == "ACTIVE"
        assert session.scalar(select(func.count()).select_from(Order)) == 1
        assert session.scalar(select(func.count()).select_from(CustomerEvent)) == 1
        assert session.scalar(select(func.count()).select_from(DatasetVersion)) == 5
        channels = session.scalars(select(CustomerChannel)).all()
        assert len(channels) == 3
        assert {c.channel for c in channels if c.consent} == {"EMAIL"}
    logs = client.get("/api/v1/audit-logs?action=DATA_IMPORTED").json()
    assert logs["total"] == 5 and "demo@example.invalid" not in str(logs)


def test_invalid_file_is_all_or_nothing(client, database, dataset_id):
    execute(client, database, preview(client, dataset_id, "customers"))
    batch = preview(client, dataset_id, "orders", (FIXTURES / "invalid_orders.csv").read_bytes())
    assert batch["status"] == "INVALID" and batch["summary"]["error_count"] == 2
    assert {e["row"] for e in batch["summary"]["errors"]} == {2, 3}
    assert client.post(f"/api/v1/data/import/{batch['import_batch_id']}/commit").status_code == 409
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0


def test_upsert_refund_and_immutable_events(client, database, dataset_id):
    for kind in ("customers", "orders", "events"):
        execute(client, database, preview(client, dataset_id, kind))
    changed = (FIXTURES / "orders.csv").read_bytes().replace(b"COMPLETED", b"REFUNDED")
    assert preview(client, dataset_id, "orders", changed)["status"] == "INVALID"
    execute(client, database, preview(client, dataset_id, "orders", changed, mode="upsert"))
    with database.sessions() as session:
        customer = session.scalar(select(Customer))
        assert customer.order_count == 0 and customer.total_purchase_amount == 0
        assert customer.last_purchase_at is None and customer.status == "DORMANT"
    changed_event = (FIXTURES / "events.csv").read_bytes().replace(b"PURCHASE", b"VIEW")
    assert preview(client, dataset_id, "events", changed_event, mode="upsert")["status"] == "INVALID"
    partial = changed.replace(b"REFUNDED", b"PARTIALLY_REFUNDED")
    assert preview(client, dataset_id, "orders", partial, mode="upsert")["status"] == "INVALID"


def test_stale_preview_revalidates_and_future_orders_excluded(client, database, dataset_id):
    first = preview(client, dataset_id, "customers")
    conflicting = (FIXTURES / "customers.csv").read_bytes().replace(b",Demo,", b",Changed,")
    second = preview(client, dataset_id, "customers", conflicting)
    execute(client, database, first)
    client.post(f"/api/v1/data/import/{second['import_batch_id']}/commit")
    run_once(database, SETTINGS)
    failed = client.get(f"/api/v1/data/import/{second['import_batch_id']}").json()
    assert failed["status"] == "FAILED"
    future = (FIXTURES / "orders.csv").read_bytes().replace(b"2026-09-01", b"2027-01-01")
    execute(client, database, preview(client, dataset_id, "orders", future))
    with database.sessions() as session:
        assert session.scalar(select(Customer)).order_count == 0
        assert session.scalar(select(Customer)).name == "Demo"
    response = client.post("/api/v1/data/import/products/preview", content=(FIXTURES / "products.csv").read_bytes(),
        headers={"Content-Type": "text/csv"}, params={"dataset_id": dataset_id, "reference_at": (REFERENCE + timedelta(days=1)).isoformat()})
    assert response.status_code == 409


def test_transaction_failure_and_retry(client, database, dataset_id, monkeypatch):
    batch = preview(client, dataset_id, "customers")
    queued = client.post(f"/api/v1/data/import/{batch['import_batch_id']}/commit").json()
    original = imports.record_change
    def fail_audit(*args, **kwargs):
        raise RuntimeError("injected failure")
    monkeypatch.setattr(imports, "record_change", fail_audit)
    run_once(database, SETTINGS)
    with database.sessions.begin() as session:
        assert session.scalar(select(func.count()).select_from(Customer)) == 0
        assert session.scalar(select(func.count()).select_from(DatasetVersion)) == 0
        assert session.get(ImportBatch, UUID(batch["import_batch_id"])).status == "QUEUED"
        session.execute(update(Job).where(Job.id == UUID(queued["job_id"])).values(available_at=REFERENCE))
    monkeypatch.setattr(imports, "record_change", original)
    run_once(database, SETTINGS)
    assert client.get(f"/api/v1/data/import/{batch['import_batch_id']}").json()["status"] == "COMPLETED"
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Customer)) == 1
        assert session.scalar(select(Job)).attempt == 2


def test_upload_limits_bom_and_retention(client, database, dataset_id, monkeypatch):
    content = (FIXTURES / "products.csv").read_bytes()
    batch = preview(client, dataset_id, "products", b"\xef\xbb\xbf" + content)
    assert batch["status"] == "PREVIEW"
    with database.sessions.begin() as session:
        row = session.get(ImportBatch, UUID(batch["import_batch_id"]))
        row.expires_at = REFERENCE - timedelta(days=1)
    assert client.post(f"/api/v1/data/import/{batch['import_batch_id']}/commit").status_code == 409
    with database.sessions.begin() as session:
        assert cleanup(session) == 1
    queued = preview(client, dataset_id, "products")
    client.post(f"/api/v1/data/import/{queued['import_batch_id']}/commit")
    with database.sessions.begin() as session:
        session.get(ImportBatch, UUID(queued["import_batch_id"])).expires_at = REFERENCE - timedelta(days=1)
    with database.sessions.begin() as session:
        assert cleanup(session) == 0
    monkeypatch.setattr(imports, "MAX_BYTES", 5)
    result = client.post("/api/v1/data/import/products/preview", content=content,
        headers={"Content-Type": "text/csv"}, params={"dataset_id": dataset_id, "reference_at": REFERENCE.isoformat()})
    assert result.status_code == 413


def test_seed_is_deterministic_and_never_overwrites(database):
    with database.sessions.begin() as session:
        dataset, created = seed_demo(session, seed=42, reference_at=REFERENCE)
        dataset_id = dataset.id
        assert created
    with database.sessions.begin() as session:
        original = session.scalar(select(Customer).where(Customer.dataset_id == dataset_id).order_by(Customer.external_id))
        original.name = "Visitor changed this"
        again, created = seed_demo(session, seed=42, reference_at=REFERENCE)
        assert again.id == dataset_id and not created
    with database.sessions.begin() as session:
        fresh, created = seed_demo(session, seed=42, reference_at=REFERENCE, dataset_key="fresh")
        assert fresh.id != dataset_id and created
        def metrics(id):
            return session.execute(select(Customer.external_id, Customer.order_count, Customer.total_purchase_amount,
                Customer.last_purchase_at, Customer.status).where(Customer.dataset_id == id).order_by(Customer.external_id)).all()
        assert metrics(fresh.id) == metrics(dataset_id)
        assert session.scalar(select(func.count()).select_from(Customer).where(Customer.dataset_id == dataset_id)) == 300
        assert session.scalar(select(func.count()).select_from(Order).where(Order.dataset_id == dataset_id)) == 900
        assert session.scalar(select(func.count()).select_from(CustomerEvent).where(CustomerEvent.dataset_id == dataset_id)) == 6000
        vip = session.scalar(select(Customer).where(Customer.dataset_id == dataset_id, Customer.external_id == "customer-0"))
        assert vip.status == "DORMANT" and vip.total_purchase_amount >= 300000


def test_concurrent_commit_and_dataset_isolation(client, database, dataset_id):
    from concurrent.futures import ThreadPoolExecutor
    from app.services.imports import commit_batch
    batch = preview(client, dataset_id, "customers")
    def commit(_):
        with database.sessions.begin() as session:
            return commit_batch(session, UUID(batch["import_batch_id"])).job_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(commit, range(2)))
    assert ids[0] == ids[1]
    run_once(database, SETTINGS)
    other = client.post("/api/v1/datasets", json={"name": "Other"}).json()["id"]
    invalid = preview(client, other, "orders")
    assert invalid["status"] == "INVALID"
    assert invalid["summary"]["errors"][0]["code"] == "CUSTOMER_NOT_FOUND"


def test_metric_check_and_repair(client, database, dataset_id):
    from scripts.recalculate_customers import check_metrics
    for kind in ("customers", "orders"):
        execute(client, database, preview(client, dataset_id, kind))
    with database.sessions.begin() as session:
        session.scalar(select(Customer)).total_purchase_amount = 1
    with database.sessions.begin() as session:
        assert check_metrics(session, UUID(dataset_id)) == 1
    with database.sessions.begin() as session:
        assert session.scalar(select(Customer)).total_purchase_amount == 1
        assert check_metrics(session, UUID(dataset_id), apply=True) == 1
    with database.sessions() as session:
        assert session.scalar(select(Customer)).total_purchase_amount == Decimal("300000.00")


def test_name_backfill_preserves_edits_and_is_idempotent(database):
    from scripts.backfill_demo_names import backfill
    with database.sessions.begin() as session:
        dataset, _ = seed_demo(session, seed=42, reference_at=REFERENCE)
        rows = session.scalars(select(Customer).where(Customer.dataset_id == dataset.id).order_by(Customer.external_id)).all()
        rows[0].name = "dormant_vip-0"
        rows[1].name = "Visitor edited"
        rows[2].name = None
        session.flush()
        assert backfill(session, dataset.id) == 2
        assert rows[0].name == "dormant_vip-0"
        assert backfill(session, dataset.id, apply=True) == 2
        session.flush()
        assert backfill(session, dataset.id, apply=True) == 0
        assert rows[1].name == "Visitor edited"
        with pytest.raises(ValueError):
            backfill(session, dataset.id, seed=43)
