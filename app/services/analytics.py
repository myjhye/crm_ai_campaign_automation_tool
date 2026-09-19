"""Read-only snapshot services shared by HTTP and future AI aggregate tools."""
from decimal import Decimal
from app.core.errors import AppError
from app.repositories import analytics as repository
from app.repositories.imports import data_version
from app.services.datasets import require_dataset
from app.schemas.analytics import CustomerRow
from app.domain.analytics.rfm import scores


def snapshot(session, query):
    session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
    dataset = require_dataset(session, query.dataset_id)
    version = data_version(session, query.dataset_id)
    if query.data_version is not None and query.data_version != version:
        raise AppError("DATA_VERSION_CONFLICT", "Data changed. Reload all dashboard panels.")
    return dataset, {"dataset_id": query.dataset_id, "reference_at": query.end, "data_version": version}


def mask_email(contact):
    if not contact: return None
    if "@" not in contact: return "***"
    local, domain = contact.rsplit("@", 1)
    return f"{local[:1]}***@{domain}"


def customer_row(row, email, reference):
    data = dict(row)
    count, amount = data["order_count"], data["total_purchase_amount"]
    data.update(email=mask_email(email),
        average_order_amount=(amount / count).quantize(Decimal("0.01")) if count else None,
        days_since_last_purchase=(reference - data["last_purchase_at"]).days if data["last_purchase_at"] else None)
    return CustomerRow(**data)


def list_customers(session, query):
    _, meta = snapshot(session, query)
    rows, total = repository.list_customers(session, query)
    channels = repository.channels(session, query.dataset_id, [row["id"] for row in rows])
    emails = {c.customer_id: c.contact for c in channels if c.channel == "EMAIL"}
    return {**meta, "items": [customer_row(row, emails.get(row["id"]), query.end) for row in rows],
            "total": total, "page": query.page, "page_size": query.page_size}


def require_customer(session, query, customer_id):
    row = repository.get_customer(session, query.dataset_id, customer_id, query.end)
    if row is None: raise AppError("NOT_FOUND", "Customer not found at this reference time.", 404)
    return row


def detail(session, query, customer_id):
    _, meta = snapshot(session, query)
    row = require_customer(session, query, customer_id)
    channels = repository.channels(session, query.dataset_id, [customer_id])
    email = next((c.contact for c in channels if c.channel == "EMAIL"), None)
    customer = customer_row(row, email, query.end)
    category = repository.preferred_category(session, query.dataset_id, customer_id, query.end)
    return {**meta, "customer": customer.model_dump(mode="json"),
            "channels": [{"channel": c.channel, "consent": c.consent, "consent_changed_at": c.consent_changed_at,
                          "is_valid": c.is_valid, "hard_bounce": c.hard_bounce} for c in channels],
            "channel_state": "current", "preferred_category": category[0] if category else None,
            "rfm": scores(customer.days_since_last_purchase, customer.order_count, customer.total_purchase_amount),
            "fatigue": {"status": "not_ready", "value": None, "reason": "DELIVERY_HISTORY_NOT_IMPLEMENTED"}}


def customer_events(session, query, customer_id):
    _, meta = snapshot(session, query)
    require_customer(session, query, customer_id)
    rows, total = repository.events(session, query, customer_id)
    return {**meta, "items": [dict(row) for row in rows], "total": total, "page": query.page, "page_size": query.page_size}


def pending_history(session, query, customer_id, kind):
    _, meta = snapshot(session, query)
    require_customer(session, query, customer_id)
    return {**meta, "status": "not_ready", "reason": f"{kind.upper()}_NOT_IMPLEMENTED", "items": [], "total": None}


def metric(value, previous, unit, numerator=None, denominator=None):
    difference = round(value - previous, 4) if value is not None and previous is not None else None
    return {"value": value, "previous_value": previous, "unit": unit,
        "reason": "NO_DENOMINATOR" if value is None else None,
        "difference": difference, "difference_unit": "percentage_point" if unit == "percent" else "customers",
        "relative_change": round((value - previous) / previous * 100, 4) if value is not None and previous else None,
        "numerator": numerator, "denominator": denominator}


def overview(session, query):
    dataset, meta = snapshot(session, query)
    previous_start = query.start - (query.end - query.start)
    now = repository.period_metrics(session, query.dataset_id, query.start, query.end)
    before = repository.period_metrics(session, query.dataset_id, previous_start, query.start)
    metrics = {key: metric(now[key], before[key], "customers") for key in (
        "total_customers", "new_customers", "active_customers", "dormant_customers")}
    for name, numerator, denominator in [("purchase_conversion_rate", "active_buyers", "active_customers"),
                                          ("repeat_purchase_rate", "repeat_buyers", "buyers")]:
        ratio = lambda values: round(values[numerator] / values[denominator] * 100, 4) if values[denominator] else None
        metrics[name] = metric(ratio(now), ratio(before), "percent", now[numerator], now[denominator])
    metrics["crm_revenue"] = {"value": None, "reason": "not_ready", "unit": "KRW", "difference_unit": "KRW"}
    return {**meta, "source": dataset.source, "period": {"from": query.start, "to": query.end},
            "previous_period": {"from": previous_start, "to": query.start}, "includes_withdrawn": True, "metrics": metrics}


def funnel(session, query):
    _, meta = snapshot(session, query)
    counts = repository.funnel_counts(session, query.dataset_id, query.start, query.end)
    return {**meta, "period": {"from": query.start, "to": query.end}, "steps": [
        {"name": name, "count": count} for name, count in zip(("view", "cart", "purchase"), counts)],
        "rule": "VIEW < CART < PURCHASE, distinct customers within [from,to)"}


def distribution(session, query):
    _, meta = snapshot(session, query)
    counts = repository.status_distribution(session, query.dataset_id, query.end)
    return {**meta, "period": {"from": query.start, "to": query.end}, "customer_statuses": [
        {"status": status, "count": counts.get(status, 0)} for status in ("ACTIVE", "CHURN_RISK", "DORMANT", "WITHDRAWN")],
        "segments": {"status": "not_ready", "items": [], "reason": "SEGMENT_MEMBERSHIP_NOT_IMPLEMENTED"}}
