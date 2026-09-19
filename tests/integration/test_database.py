"""Real PostgreSQL tests; each test gets a disposable schema in a *_test DB."""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import Database
from app.main import create_app
from app.models import AuditLog, Customer, CustomerChannel, Dataset, Job, Order
from app.services.jobs import LeaseLost, claim_job, enqueue, finish, renew_lease
from app.workers.runner import run_once

pytestmark = pytest.mark.postgres



def migrate(db, revision):
    config = Config("alembic.ini")
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)



def add_dataset(db):
    with db.sessions.begin() as session:
        dataset = Dataset(name="Integration fixture")
        session.add(dataset)
        session.flush()
        return dataset.id


def add_job(db, **kwargs):
    dataset_id = kwargs.pop("dataset_id", None) or add_dataset(db)
    with db.sessions.begin() as session:
        return enqueue(session, dataset_id=dataset_id, kind="system.check",
                       key=kwargs.pop("key", str(uuid4())), payload=kwargs.pop("payload", {}), **kwargs)


def expire(db, job):
    with db.sessions.begin() as session:
        session.execute(update(Job).where(Job.id == job.id).values(
            lease_until=func.now() - timedelta(seconds=1)))


def test_migrations_empty_and_incremental(raw_database):
    migrate(raw_database, "001")
    assert set(inspect(raw_database.engine).get_table_names()) == {"alembic_version", "datasets", "audit_logs"}
    dataset_id = uuid4()
    with raw_database.engine.begin() as connection:
        connection.execute(text("INSERT INTO datasets (id,name,source) VALUES (:id,'Integration fixture','DEMO')"), {"id": dataset_id})
    migrate(raw_database, "002")
    assert "orders" in inspect(raw_database.engine).get_table_names()
    migrate(raw_database, "head")
    with raw_database.sessions() as session:
        assert session.get(Dataset, dataset_id).name == "Integration fixture"
    config = Config("alembic.ini")
    with raw_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.check(config)


def test_constraints_and_utc_numeric(database):
    first, second = add_dataset(database), add_dataset(database)
    now = datetime(2026, 9, 18, 9, tzinfo=timezone(timedelta(hours=9)))
    with database.sessions.begin() as session:
        customer = Customer(dataset_id=first, external_id="c1", signup_at=now)
        session.add(customer)
        session.flush()
        customer_id = customer.id
        session.add(Order(dataset_id=first, external_id="o1", customer_id=customer_id,
                          purchased_at=now, status="COMPLETED", amount=Decimal("300000.10")))
    with database.sessions() as session:
        order = session.scalar(select(Order))
        assert order.amount == Decimal("300000.10")
        assert order.purchased_at.hour == 0
        assert order.purchased_at.utcoffset() == timedelta(0)
    invalid = [
        Customer(dataset_id=first, external_id="c1", signup_at=now),
        Customer(dataset_id=first, external_id="bad", signup_at=now, total_purchase_amount=-1),
        CustomerChannel(dataset_id=second, customer_id=customer_id, channel="EMAIL"),
        Order(dataset_id=first, external_id="bad", customer_id=uuid4(), purchased_at=now,
              status="COMPLETED", amount=1),
    ]
    for row in invalid:
        with pytest.raises(IntegrityError), database.sessions.begin() as session:
            session.add(row)
            session.flush()
    with database.sessions.begin() as session:
        session.add(Customer(dataset_id=second, external_id="c1", signup_at=now))


def test_enqueue_is_atomic_and_idempotent(database):
    dataset_id = add_dataset(database)
    with pytest.raises(RuntimeError), database.sessions.begin() as session:
        enqueue(session, dataset_id=dataset_id, kind="system.check", key="rollback", payload={})
        session.add(AuditLog(dataset_id=dataset_id, actor_type="VISITOR", action="ROLLBACK"))
        raise RuntimeError()
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0
    a = add_job(database, dataset_id=dataset_id, key="same")
    b = add_job(database, dataset_id=dataset_id, key="same")
    assert a.id == b.id
    with pytest.raises(AppError):
        add_job(database, dataset_id=dataset_id, key="same", payload={"delay_seconds": 1})


def test_concurrent_claim_and_stale_completion_rollback(database):
    job = add_job(database)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim_job(database.sessions, 30), range(2)))
    assert sum(claim is not None for claim in claims) == 1
    old = next(claim for claim in claims if claim is not None)
    assert renew_lease(database.sessions, old.id, old.lease_token, 30)
    expire(database, old)
    current = claim_job(database.sessions, 30)
    assert current.id == job.id and current.attempt == 2
    assert not renew_lease(database.sessions, old.id, old.lease_token, 30)
    with pytest.raises(LeaseLost), database.sessions.begin() as session:
        session.add(AuditLog(dataset_id=job.dataset_id, actor_type="SYSTEM", action="STALE"))
        session.flush()
        finish(session, old.id, old.lease_token, {})
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_worker_success_retry_and_exhaustion(database):
    settings = Settings(_env_file=None)
    job = add_job(database)
    assert run_once(database, settings)
    assert not run_once(database, settings)
    with database.sessions() as session:
        assert session.get(Job, job.id).progress == 100
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1
    bad = add_job(database, payload={"unexpected": True}, max_attempts=2)
    run_once(database, settings)
    with database.sessions.begin() as session:
        row = session.get(Job, bad.id)
        assert row.status == "PENDING" and row.attempt == 1
        row.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    run_once(database, settings)
    with database.sessions() as session:
        assert session.get(Job, bad.id).status == "FAILED"
    crashed = add_job(database, max_attempts=1)
    claimed = claim_job(database.sessions, 30)
    expire(database, claimed)
    assert claim_job(database.sessions, 30) is None
    with database.sessions() as session:
        assert session.get(Job, crashed.id).error_code == "LEASE_EXHAUSTED"


def test_readiness_and_job_api(database):
    app = create_app(Settings(_env_file=None, database_url=None))
    app.state.database = database
    job = add_job(database)
    with TestClient(app) as client:
        assert client.get("/api/v1/ready").status_code == 200
        response = client.get(f"/api/v1/jobs/{job.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "PENDING"
        assert "payload" not in response.json() and "lease_token" not in response.json()
        assert client.get(f"/api/v1/jobs/{uuid4()}").status_code == 404
        assert client.get("/api/v1/jobs/not-a-uuid").status_code == 422


def test_concurrent_enqueue_creates_one_job(database):
    dataset_id = add_dataset(database)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: add_job(database, dataset_id=dataset_id, key="concurrent"), range(2)))
    assert results[0].id == results[1].id
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1


def test_process_crash_heartbeat_and_recovery(database):
    job = add_job(database, payload={"delay_seconds": 8})
    env = os.environ.copy()
    env["DATABASE_URL"] = make_url(env["TEST_DATABASE_URL"]).update_query_dict(
        {"options": f"-c search_path={database.test_schema}"}
    ).render_as_string(hide_password=False)
    env.update(WORKER_LEASE_SECONDS="3", WORKER_HEARTBEAT_SECONDS="0.5")
    process = subprocess.Popen([sys.executable, "-m", "app.workers.runner", "--once"],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with database.sessions() as session:
                if session.get(Job, job.id).status == "RUNNING":
                    break
            assert process.poll() is None, "Worker exited before claiming job"
            time.sleep(0.1)
        else:
            pytest.fail("Worker did not claim job")
        # Beyond the initial lease, a live heartbeat must prevent another claim.
        time.sleep(3.5)
        assert claim_job(database.sessions, 3) is None
    finally:
        process.terminate()
        process.wait(timeout=10)
    time.sleep(3.2)
    assert run_once(database, Settings(_env_file=None))
    with database.sessions() as session:
        result = session.get(Job, job.id)
        assert result.status == "SUCCEEDED" and result.attempt == 2
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1
