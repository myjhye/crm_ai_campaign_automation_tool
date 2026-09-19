from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from app.main import create_app
from app.core.config import Settings
from app.models.customers import Customer, CustomerChannel, Order, CustomerEvent, Product, OrderItem
from app.models.datasets import Dataset
from app.models.jobs import DatasetVersion

pytestmark = pytest.mark.postgres
END = datetime(2026, 9, 19, tzinfo=timezone.utc)
START = datetime(2026, 9, 1, tzinfo=timezone.utc)

@pytest.fixture
def fixture(database):
    with database.sessions.begin() as s:
        dataset = Dataset(name="Analytics fixture")
        other = Dataset(name="Other")
        s.add_all([dataset, other]); s.flush()
        ids = {}
        for name in "ABCD":
            row = Customer(dataset_id=dataset.id, external_id=name, name=name,
                signup_at=START if name == "C" else END - timedelta(days=200),
                withdrawn_at=START if name == "D" else None,
                total_purchase_amount=999999, order_count=99)
            s.add(row); s.flush(); ids[name] = row.id
        s.add(Customer(dataset_id=dataset.id, external_id="future", signup_at=END))
        s.add(Customer(dataset_id=other.id, external_id="foreign", signup_at=START))
        s.add(CustomerChannel(dataset_id=dataset.id, customer_id=ids["A"], channel="EMAIL",
            contact="alice@example.invalid", consent=True, is_valid=True))
        product = Product(dataset_id=dataset.id, external_id="p", name="P", category="home")
        s.add(product); s.flush()
        order_ids = {}
        for key, customer, at, amount, status in [
            ("a1", "A", START+timedelta(days=9), 100, "COMPLETED"),
            ("a2", "A", START+timedelta(days=10), 200, "COMPLETED"),
            ("b", "B", END-timedelta(days=80), 50, "COMPLETED"),
            ("c", "C", START+timedelta(days=2), 100, "COMPLETED"),
            ("d", "D", START+timedelta(days=3), 500, "CANCELLED"),
            ("edge", "A", END, 900, "COMPLETED")]:
            order = Order(dataset_id=dataset.id, external_id=key, customer_id=ids[customer], purchased_at=at, amount=amount, status=status)
            s.add(order); s.flush(); order_ids[key] = order.id
        s.add(OrderItem(dataset_id=dataset.id, order_id=order_ids["a1"], product_id=product.id,
                       line_id="1", quantity=1, amount=100))
        for i, (customer, kind, day) in enumerate([
            ("A", "VIEW", 1), ("A", "VIEW", 1), ("A", "CART", 2), ("A", "PURCHASE", 9),
            ("B", "CART", 1), ("B", "VIEW", 2), ("D", "VIEW", 3), ("C", "VIEW", 18)]):
            s.add(CustomerEvent(dataset_id=dataset.id, external_id=str(i), customer_id=ids[customer], event_type=kind,
                event_at=START+timedelta(days=day), order_id=order_ids["a1"] if kind == "PURCHASE" else None,
                properties={"secret": "never-return-this"}))
        s.add(DatasetVersion(dataset_id=dataset.id, version=1, reason="fixture"))
        dataset_id, other_id = dataset.id, other.id
    app = create_app(Settings(_env_file=None, database_url=None)); app.state.database = database
    with TestClient(app) as client:
        yield client, {"dataset_id": str(dataset_id), "from": START.isoformat(), "to": END.isoformat()}, ids, other_id


def test_dashboard_matches_hand_calculation(fixture):
    client, params, ids, _ = fixture
    response = client.get("/api/v1/dashboard/overview", params=params)
    assert response.status_code == 200, response.text
    body = response.json(); metrics = body["metrics"]
    assert metrics["total_customers"]["value"] == 4
    assert metrics["new_customers"]["value"] == 1
    assert metrics["active_customers"]["value"] == 3
    assert metrics["dormant_customers"]["value"] == 1
    assert metrics["purchase_conversion_rate"]["value"] == 33.3333
    assert metrics["purchase_conversion_rate"]["denominator"] == 3
    assert metrics["repeat_purchase_rate"]["value"] == 50
    assert metrics["repeat_purchase_rate"]["difference_unit"] == "percentage_point"
    assert metrics["crm_revenue"]["value"] is None and metrics["crm_revenue"]["reason"] == "not_ready"
    assert body["includes_withdrawn"] is True
    params["data_version"] = body["data_version"]
    funnel = client.get("/api/v1/dashboard/funnel", params=params).json()
    assert [r["count"] for r in funnel["steps"]] == [3, 1, 1]
    distribution = client.get("/api/v1/dashboard/segments", params=params).json()
    assert {r["status"]: r["count"] for r in distribution["customer_statuses"]} == {"ACTIVE": 2, "CHURN_RISK": 0, "DORMANT": 1, "WITHDRAWN": 1}
    assert distribution["segments"]["status"] == "not_ready"
    assert client.get("/api/v1/dashboard/funnel", params={**params, "data_version": 0}).status_code == 409


def test_customers_masking_filters_and_boundaries(fixture):
    client, params, ids, other = fixture
    response = client.get("/api/v1/customers", params={**params, "q": "alice", "sort": "total_purchase_amount"})
    assert response.status_code == 200, response.text
    body = response.json(); assert body["total"] == 1
    customer = body["items"][0]
    assert customer["email"] == "a***@example.invalid"
    assert Decimal(customer["total_purchase_amount"]) == 300 and customer["order_count"] == 2
    assert Decimal(customer["average_order_amount"]) == 150
    assert "alice@example.invalid" not in response.text
    for cohort, expected in [("active",3), ("new",1), ("purchased",2), ("repeat",1), ("view",3), ("cart",1), ("purchase",1)]:
        result = client.get("/api/v1/customers", params={**params, "cohort": cohort}).json()
        assert result["total"] == expected, (cohort, result)
    assert client.get("/api/v1/customers", params={**params, "status": "DORMANT"}).json()["total"] == 1
    assert client.get("/api/v1/customers", params={**params, "page": 9}).json()["items"] == []
    assert client.get("/api/v1/customers", params={**params, "sort": "drop table"}).status_code == 422
    assert client.get("/api/v1/customers", params={**params, "q": "%"}).json()["total"] == 0
    assert client.get("/api/v1/customers", params={**params, "to": "2026-09-19T00:00:00"}).status_code == 422
    detail = client.get(f"/api/v1/customers/{ids['A']}", params=params)
    assert detail.status_code == 200 and "alice@example.invalid" not in detail.text
    assert detail.json()["preferred_category"] == "home"
    assert detail.json()["fatigue"]["status"] == "not_ready"
    events = client.get(f"/api/v1/customers/{ids['A']}/events", params=params)
    assert events.json()["total"] == 4 and "never-return-this" not in events.text
    for kind in ("deliveries", "segments"):
        result = client.get(f"/api/v1/customers/{ids['A']}/{kind}", params=params).json()
        assert result["status"] == "not_ready" and result["total"] is None
    assert client.get(f"/api/v1/customers/{ids['A']}", params={**params, "dataset_id": str(other)}).status_code == 404


def test_empty_denominators_and_bounded_query_count(fixture, database):
    client, params, ids, other = fixture
    empty = client.get("/api/v1/dashboard/overview", params={**params, "from": "2020-01-01T00:00:00Z", "to": "2020-02-01T00:00:00Z"}).json()
    assert empty["metrics"]["total_customers"]["value"] == 0
    assert empty["metrics"]["purchase_conversion_rate"]["reason"] == "NO_DENOMINATOR"
    statements = []
    def capture(*args): statements.append(args[2])
    event.listen(database.engine, "before_cursor_execute", capture)
    try:
        client.get("/api/v1/customers", params={**params, "page_size": 1}); small = len(statements)
        statements.clear()
        client.get("/api/v1/customers", params={**params, "page_size": 100}); large = len(statements)
    finally: event.remove(database.engine, "before_cursor_execute", capture)
    assert small == large == 5


def test_status_day_boundaries(database):
    with database.sessions.begin() as s:
        dataset = Dataset(name="Boundary"); s.add(dataset); s.flush(); dataset_id = dataset.id
        for days in (29, 30, 59, 60):
            s.add(Customer(dataset_id=dataset_id, external_id=str(days), signup_at=END-timedelta(days=days)))
    app = create_app(Settings(_env_file=None, database_url=None)); app.state.database = database
    with TestClient(app) as client:
        response = client.get("/api/v1/customers", params={"dataset_id":str(dataset_id), "from":START.isoformat(), "to":END.isoformat()})
        assert response.status_code == 200, response.text
        assert {r["external_id"]:r["status"] for r in response.json()["items"]} == {"29":"ACTIVE", "30":"CHURN_RISK", "59":"CHURN_RISK", "60":"DORMANT"}
