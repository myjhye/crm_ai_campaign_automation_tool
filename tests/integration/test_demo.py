from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app
from app.models import AuditLog, Dataset
from app.schemas.datasets import DatasetUpdate
from app.services import audit, datasets

pytestmark = pytest.mark.postgres


@pytest.fixture
def client(database):
    app = create_app(Settings(_env_file=None, database_url=None))
    app.state.database = database
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_public_dataset_flow_and_audit(client):
    assert client.get("/api/v1/datasets").json()["total"] == 0
    created = client.post("/api/v1/datasets", json={"name": "  Demo  "})
    assert created.status_code == 201
    row = created.json()
    assert row["name"] == "Demo" and row["version"] == 1 and row["source"] == "DEMO"
    dataset_id = row["id"]
    changed = client.put(f"/api/v1/datasets/{dataset_id}", json={"name": "Updated", "version": 1})
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert client.get(f"/api/v1/datasets/{dataset_id}").json()["name"] == "Updated"
    assert client.get("/api/v1/datasets?page=2&page_size=1").json()["items"] == []
    assert client.get("/api/v1/datasets?page=2&page_size=1").json()["total"] == 1
    logs = client.get(f"/api/v1/audit-logs?dataset_id={dataset_id}").json()
    assert logs["total"] == 2
    assert logs["items"][0]["previous_version"] == 1
    assert logs["items"][0]["new_version"] == 2
    assert logs["items"][0]["request_id"] == changed.headers["x-request-id"]
    assert logs["items"][1]["request_id"] == created.headers["x-request-id"]
    assert all(entry["actor_type"] == "VISITOR" for entry in logs["items"])
    no_op = client.put(f"/api/v1/datasets/{dataset_id}", json={"name": "Updated", "version": 2})
    assert no_op.json()["version"] == 2
    stale = client.put(f"/api/v1/datasets/{dataset_id}", json={"name": "Lost", "version": 1})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "VERSION_CONFLICT"
    assert client.get(f"/api/v1/audit-logs?dataset_id={dataset_id}").json()["total"] == 2
    for body in ({"name": " "}, {"name": "x", "actor_type": "SYSTEM"}, {"name": "x", "source": "UPLOADED"}):
        assert client.post("/api/v1/datasets", json=body).status_code == 422
    assert client.get(f"/api/v1/datasets/{uuid4()}").status_code == 404
    assert client.get("/api/v1/datasets/not-uuid").status_code == 422
    assert client.get("/api/v1/datasets?page_size=101").status_code == 422
    assert client.get("/api/v1/audit-logs?actor_type=ADMIN").status_code == 422


def test_audit_failure_rolls_back_create_and_update(client, database, monkeypatch):
    original = client.post("/api/v1/datasets", json={"name": "Original"}).json()

    def broken_audit(session, **kwargs):
        session.add(AuditLog(dataset_id=kwargs["dataset_id"], actor_type="INVALID", action="FAIL"))
        session.flush()

    monkeypatch.setattr(audit, "record_change", broken_audit)
    assert client.post("/api/v1/datasets", json={"name": "Rollback"}).status_code == 500
    assert client.put(f"/api/v1/datasets/{original['id']}", json={"name": "Rollback", "version": 1}).status_code == 500
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Dataset)) == 1
        assert session.scalar(select(Dataset)).name == "Original"
        assert session.scalar(select(Dataset)).version == 1
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_concurrent_updates_only_one_wins(client, database):
    row = client.post("/api/v1/datasets", json={"name": "Concurrent"}).json()

    def update(name):
        with database.sessions() as session:
            try:
                datasets.update_dataset(session, row["id"], DatasetUpdate(name=name, version=1), uuid4())
                return 200
            except AppError as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, ["First", "Second"])) == [200, 409]
    assert client.get("/api/v1/audit-logs?action=DATASET_UPDATED").json()["total"] == 1


def test_audit_filters_and_no_raw_data(client, database):
    a = client.post("/api/v1/datasets", json={"name": "private@example.com"}).json()
    b = client.post("/api/v1/datasets", json={"name": "Other"}).json()
    with database.sessions.begin() as session:
        session.add(AuditLog(dataset_id=a["id"], actor_type="SYSTEM", action="OLD_EVENT",
                             details={"contact": "private@example.com", "secret": "internal-key"}))
    response = client.get("/api/v1/audit-logs")
    assert "private@example.com" not in response.text and "internal-key" not in response.text
    assert "details" not in response.json()["items"][0]
    filtered = client.get(f"/api/v1/audit-logs?dataset_id={a['id']}&actor_type=SYSTEM&action=OLD_EVENT")
    assert filtered.json()["total"] == 1
    assert client.get(f"/api/v1/audit-logs?resource_id={b['id']}").json()["total"] == 1
    assert client.get(f"/api/v1/audit-logs?dataset_id={uuid4()}").json()["items"] == []


def test_upgrade_preserves_existing_dataset(raw_database):
    cfg = Config("alembic.ini")
    dataset_id = uuid4()
    with raw_database.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "003")
        connection.execute(text("INSERT INTO datasets (id,name,source) VALUES (:id,'Existing','DEMO')"), {"id": dataset_id})
        command.upgrade(cfg, "head")
        row = connection.execute(text("SELECT version, created_at=updated_at AS unchanged FROM datasets WHERE id=:id"), {"id": dataset_id}).one()
        assert row.version == 1 and row.unchanged
        command.check(cfg)


def test_system_hidden_and_populated_default_across_pages(client, database):
    from datetime import datetime, timezone
    from app.models.customers import Customer
    with database.sessions.begin() as session:
        populated = Dataset(name="Existing edited sample")
        system = Dataset(name="Worker diagnostic", purpose="SYSTEM")
        session.add_all([populated, system])
        session.flush()
        populated_id, system_id = populated.id, system.id
        session.add(Customer(dataset_id=populated.id, external_id="one", signup_at=datetime.now(timezone.utc)))
        session.add_all([Dataset(name=f"Empty {i}") for i in range(105)])
    page = client.get("/api/v1/datasets?page_size=100").json()
    assert page["total"] == 106
    assert page["items"][0]["id"] == str(populated_id)
    assert page["items"][0]["customer_count"] == 1
    assert page["items"][0]["order_count"] == 0
    assert all(row["purpose"] == "ANALYSIS" for row in page["items"])
    assert "Worker diagnostic" not in str(page)
    assert client.get(f"/api/v1/datasets/{system_id}").status_code == 404
    assert client.put(f"/api/v1/datasets/{system_id}", json={"name": "Changed", "version": 1}).status_code == 404
    assert client.post("/api/v1/datasets", json={"name": "Hidden", "purpose": "SYSTEM"}).status_code == 422
    detail = client.get(f"/api/v1/datasets/{populated_id}").json()
    assert detail["name"] == "Existing edited sample" and detail["customer_count"] == 1


def test_purpose_migration_preserves_names(raw_database):
    cfg = Config("alembic.ini")
    with raw_database.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "003b")
        for name in ("Worker diagnostic", "Demo small / seed 42", "My edited name"):
            connection.execute(text("INSERT INTO datasets(id,name,source) VALUES (:id,:name,'DEMO')"), {"id": uuid4(), "name": name})
        command.upgrade(cfg, "003c")
        rows = dict(connection.execute(text("SELECT name,purpose FROM datasets")).all())
        assert rows == {"Worker diagnostic": "SYSTEM", "Demo small / seed 42": "ANALYSIS", "My edited name": "ANALYSIS"}
def test_legacy_sample_name_translation_is_narrow(raw_database):
    cfg = Config("alembic.ini")
    with raw_database.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "003c")
        for name, version in (("Demo small / seed 42", 1), ("Demo demo / seed 42", 1), ("Edited sample", 1), ("Demo small / seed 42", 2)):
            connection.execute(text("INSERT INTO datasets(id,name,source,version) VALUES (:id,:name,'DEMO',:version)"), {"id": uuid4(), "name": name, "version": version})
        command.upgrade(cfg, "head")
        names = connection.execute(text("SELECT name FROM datasets")).scalars().all()
        assert sorted(names) == sorted(["체험용 소형 샘플", "체험용 전체 샘플", "Edited sample", "Demo small / seed 42"])
