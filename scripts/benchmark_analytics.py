"""Benchmark demo-sized analytics in an isolated schema of an existing *_test DB."""
import json
import time
from statistics import median
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from scripts.seed_demo import seed_demo


def main():
    settings = Settings()
    if not settings.database_url: raise SystemExit("DATABASE_URL required")
    url = make_url(settings.database_url.get_secret_value())
    url = url.set(database=url.database + "_test")
    assert url.database.endswith("_test")
    db = Database(url.render_as_string(hide_password=False))
    schema = "test_benchmark_" + uuid4().hex
    with db.engine.begin() as connection: connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    db.dispose()
    @event.listens_for(db.engine, "connect")
    def setup(connection, record):
        with connection.cursor() as cursor: cursor.execute(f'SET search_path TO "{schema}"')
        connection.commit()
    try:
        cfg = Config("alembic.ini")
        with db.engine.begin() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
        reference = datetime(2026, 9, 19, tzinfo=timezone.utc)
        started = time.perf_counter()
        with db.sessions.begin() as session:
            dataset, _ = seed_demo(session, seed=42, reference_at=reference, size="demo")
            dataset_id = dataset.id
        print(json.dumps({"seed_seconds": round(time.perf_counter()-started, 2)}), flush=True)
        with db.engine.begin() as connection:
            for table in ("customers", "orders", "customer_channels", "customer_events", "products", "order_items", "dataset_versions"):
                connection.execute(text(f'ANALYZE {table}'))
        app = create_app(Settings(_env_file=None, database_url=None)); app.state.database = db
        statements = []
        def count(*args): statements.append(args[2])
        event.listen(db.engine, "before_cursor_execute", count)
        results = {}
        with TestClient(app) as client:
            for path in ("customers", "dashboard/overview", "dashboard/funnel", "dashboard/segments"):
                times, counts = [], []
                for _ in range(3):
                    statements.clear(); started = time.perf_counter()
                    response = client.get(f"/api/v1/{path}", params={"dataset_id":str(dataset_id), "from":"2026-09-01T00:00:00Z", "to": reference.isoformat()})
                    assert response.status_code == 200, response.text
                    times.append((time.perf_counter()-started)*1000); counts.append(len(statements))
                    if path == "customers": assert response.json()["total"] == 10000
                results[path] = {"median_ms":round(median(times),2), "sql_count":counts}
        event.remove(db.engine, "before_cursor_execute", count)
        print(json.dumps(results, indent=2), flush=True)
    finally:
        with db.engine.begin() as connection: connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        db.dispose()

if __name__ == "__main__": main()
