"""CSV staging and atomic merges; caller owns every transaction."""
import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.core.errors import AppError
from app.domain.analytics.customers import customer_status
from app.models.customers import Customer, Product, Order, OrderItem, CustomerEvent
from app.models.jobs import ImportBatch, DatasetVersion
from app.schemas.imports import SCHEMAS
from app.repositories.imports import keyed, data_version
from app.repositories import imports as repository
from app.services.datasets import require_dataset
from app.services.jobs import enqueue
from app.services.audit import record_change

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 200_000
MAX_ERRORS = 100
MODELS = {"customers": Customer, "products": Product, "orders": Order,
          "order_items": OrderItem, "events": CustomerEvent}


def parse(kind, content):
    if len(content) > MAX_BYTES:
        raise AppError("IMPORT_TOO_LARGE", "CSV exceeds 20 MiB.", 413)
    schema = SCHEMAS[kind]
    errors, rows = [], []
    error_count = 0
    def error(row, code, field=None):
        nonlocal error_count
        error_count += 1
        if len(errors) < MAX_ERRORS:
            errors.append({"row": row, "code": code, "field": field})
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        headers = reader.fieldnames or []
        if kind == "customers" and "marketing_consent" in headers:
            headers = ["email_consent" if h == "marketing_consent" else h for h in headers]
            reader.fieldnames = headers
        required = {name for name, field in schema.model_fields.items() if field.is_required()}
        if len(headers) != len(set(headers)) or not required.issubset(headers) or set(headers) - schema.model_fields.keys():
            error(1, "INVALID_COLUMNS")
            return [], errors, error_count
        for number, raw in enumerate(reader, start=2):
            if number - 1 > MAX_ROWS:
                raise AppError("IMPORT_TOO_MANY_ROWS", "CSV exceeds 200000 records.", 413)
            if None in raw or any(value is None for value in raw.values()):
                error(number, "COLUMN_COUNT")
                continue
            try:
                values = {key: value for key, value in raw.items() if value != ""}
                if "properties" in values:
                    values["properties"] = json.loads(values["properties"])
                row = schema.model_validate(values).model_dump()
                if kind == "events":
                    row["properties"] = {k: v for k, v in row["properties"].items() if v is not None}
                rows.append((number, row))
            except (ValidationError, ValueError, TypeError):
                error(number, "INVALID_ROW")
        if not rows and not errors:
            error(2, "EMPTY_CSV")
    except (UnicodeDecodeError, csv.Error):
        error(1, "INVALID_CSV_ENCODING_OR_FORMAT")
    return rows, errors, error_count



def plan_merge(session, dataset_id, kind, rows, mode, reference_at):
    model = MODELS[kind]
    existing = keyed(session, model, dataset_id)
    customers = keyed(session, Customer, dataset_id) if kind in ("orders", "events") else {}
    orders = keyed(session, Order, dataset_id) if kind in ("order_items", "events") else {}
    products = keyed(session, Product, dataset_id) if kind == "order_items" else {}
    channels = repository.email_channels(session, dataset_id) if kind == "customers" else {}
    earliest = repository.earliest_activity(session, dataset_id, Order, Order.purchased_at) if kind == "customers" else {}
    event_earliest = repository.earliest_activity(session, dataset_id, CustomerEvent, CustomerEvent.event_at) if kind == "customers" else {}
    mutations, errors, seen = [], [], {}
    counts = {"created": 0, "updated": 0, "duplicates": 0, "error_count": 0}
    def error(number, code):
        counts["error_count"] += 1
        if len(errors) < MAX_ERRORS:
            errors.append({"row": number, "code": code, "field": None})
    for number, source in rows:
        data = dict(source)
        channel = None
        try:
            if kind == "customers":
                if data["signup_at"] > reference_at or (data["withdrawn_at"] and data["withdrawn_at"] > reference_at):
                    raise ValueError("CUSTOMER_AFTER_REFERENCE")
                channel = {"consent": data.pop("email_consent"), "contact": data.pop("email"),
                           "is_valid": data.pop("email_valid"), "hard_bounce": data.pop("hard_bounce"),
                           "consent_changed_at": data.pop("consent_changed_at")}
                # ACTIVE/RISK/DORMANT are derived, never trusted from CSV.
                data.pop("status")
                old = existing.get(data["external_id"])
                if old and any(t and t < data["signup_at"] for t in (earliest.get(old.id), event_earliest.get(old.id))):
                    raise ValueError("SIGNUP_AFTER_ACTIVITY")
            if kind in ("orders", "events"):
                customer = customers.get(data.pop("customer_external_id"))
                if customer is None:
                    raise ValueError("CUSTOMER_NOT_FOUND")
                data["customer_id"] = customer.id
                at = data["purchased_at" if kind == "orders" else "event_at"]
                if at < customer.signup_at:
                    raise ValueError("ACTIVITY_BEFORE_SIGNUP")
            if kind in ("order_items", "events"):
                external = data.pop("order_external_id", None)
                order = orders.get(external)
                if external is not None and order is None:
                    raise ValueError("ORDER_NOT_FOUND")
                data["order_id"] = order.id if order else None
                if kind == "events" and order:
                    if order.customer_id != data["customer_id"]:
                        raise ValueError("ORDER_CUSTOMER_MISMATCH")
                    if data["event_type"] == "PURCHASE" and data["event_at"] != order.purchased_at:
                        raise ValueError("PURCHASE_TIME_MISMATCH")
            if kind == "order_items":
                product = products.get(data.pop("product_external_id"))
                if product is None:
                    raise ValueError("PRODUCT_NOT_FOUND")
                data["product_id"] = product.id
            key = (data["order_id"], data["line_id"]) if kind == "order_items" else data["external_id"]
            if key in seen:
                if seen[key] != (data, channel):
                    raise ValueError("CONFLICTING_FILE_DUPLICATE")
                counts["duplicates"] += 1
                continue
            seen[key] = (data, channel)
            old = existing.get(key)
            equal = old is not None and all(getattr(old, key) == value for key, value in data.items())
            if channel is not None and old:
                old_channel = channels.get(old.id)
                equal = equal and old_channel is not None and all(getattr(old_channel, k) == v for k, v in channel.items())
            if equal:
                counts["duplicates"] += 1
                continue
            if old and (mode != "upsert" or kind == "events"):
                raise ValueError("EXISTING_CONTENT_CONFLICT")
            if old and kind == "orders" and (old.customer_id != data["customer_id"] or old.purchased_at != data["purchased_at"]):
                # Identity and chronology are immutable; status/amount may be corrected.
                raise ValueError("ORDER_IDENTITY_IMMUTABLE")
            counts["updated" if old else "created"] += 1
            mutations.append((old.id if old else uuid4(), old is not None, data, channel))
        except ValueError as exc:
            error(number, str(exc))
    counts["errors"] = errors
    return mutations, counts


def recalculate(session, dataset_id, reference_at, customer_ids=None):
    if customer_ids is not None and len(customer_ids) > 5000:
        ids = list(customer_ids)
        for start in range(0, len(ids), 5000):
            recalculate(session, dataset_id, reference_at, ids[start:start + 5000])
        return
    customers, totals = repository.customers_and_totals(session, dataset_id, reference_at, customer_ids)
    for customer in customers:
        count, amount, last = totals.get(customer.id, (0, 0, None))
        customer.order_count = count
        customer.total_purchase_amount = amount
        customer.last_purchase_at = last
        customer.status = customer_status(signup_at=customer.signup_at, reference_at=reference_at,
                                          last_purchase_at=last, withdrawn_at=customer.withdrawn_at).value
    session.flush()


def apply_merge(session, dataset_id, kind, mutations, reference_at):
    model = MODELS[kind]
    new, changed, channel_rows, affected = [], [], [], set()
    for row_id, exists, data, channel in mutations:
        values = {"id": row_id, **data}
        if exists:
            changed.append(values)
        else:
            new.append({**values, "dataset_id": dataset_id})
        if kind == "customers":
            affected.add(row_id)
            channel_rows.append({"id": uuid4(), "dataset_id": dataset_id, "customer_id": row_id,
                                 "channel": "EMAIL", **channel})
        elif kind == "orders":
            affected.add(data["customer_id"])
    repository.persist(session, model, new, changed, channel_rows)
    if affected:
        recalculate(session, dataset_id, reference_at, affected)



def preview(session, *, dataset_id, kind, content, mode, reference_at, request_id):
    dataset = require_dataset(session, dataset_id, lock=True)
    if dataset.reference_at is not None and dataset.reference_at != reference_at:
        raise AppError("REFERENCE_CONFLICT", "Use the dataset reference_at for every import.")
    rows, errors, error_count = parse(kind, content)
    _, summary = plan_merge(session, dataset_id, kind, rows, mode, reference_at)
    summary["errors"] = (errors + summary["errors"])[:MAX_ERRORS]
    summary["error_count"] += error_count
    summary["reference_at"] = reference_at.isoformat()
    summary["data_version"] = data_version(session, dataset_id)
    batch = ImportBatch(dataset_id=dataset_id, kind=kind, content=content,
                        file_hash=hashlib.sha256(content).hexdigest(), summary=summary,
                        status="INVALID" if summary["error_count"] else "PREVIEW",
                        options={"mode": mode, "reference_at": reference_at.isoformat(), "request_id": str(request_id)},
                        expires_at=datetime.now(timezone.utc) + timedelta(days=7))
    session.add(batch)
    session.flush()
    return batch


def require_batch(session, batch_id, lock=False):
    batch = repository.get_batch(session, batch_id, lock)
    if batch is None:
        raise AppError("NOT_FOUND", "Import batch not found.", 404)
    return batch


def commit_batch(session, batch_id):
    batch = require_batch(session, batch_id, lock=True)
    if batch.job_id:
        return batch
    if batch.status != "PREVIEW":
        raise AppError("IMPORT_INVALID", "Only a valid preview can be committed.")
    if not batch.content or batch.expires_at <= datetime.now(timezone.utc):
        raise AppError("IMPORT_EXPIRED", "Preview expired. Upload the CSV again.")
    job = enqueue(session, dataset_id=batch.dataset_id, kind="data.import", key=str(batch.id),
                  payload={"batch_id": str(batch.id), "file_hash": batch.file_hash})
    batch.job_id, batch.status = job.id, "QUEUED"
    session.flush()
    return batch


def import_job(session, job):
    # Lock order is dataset then batch. Commit only locks batch and never waits for dataset.
    dataset = require_dataset(session, job.dataset_id, lock=True)
    batch = require_batch(session, UUID(job.payload["batch_id"]), lock=True)
    if batch.dataset_id != job.dataset_id or batch.job_id != job.id or batch.status != "QUEUED":
        raise ValueError("Invalid import job")
    if batch.content is None or hashlib.sha256(batch.content).hexdigest() != job.payload["file_hash"]:
        raise ValueError("Staged content mismatch")
    reference_at = datetime.fromisoformat(batch.options["reference_at"])
    rows, errors, error_count = parse(batch.kind, batch.content)
    mutations, summary = plan_merge(session, batch.dataset_id, batch.kind, rows, batch.options["mode"], reference_at)
    summary["errors"] = (errors + summary["errors"])[:MAX_ERRORS]
    summary["error_count"] += error_count
    if dataset.reference_at is not None and dataset.reference_at != reference_at:
        summary["error_count"] += 1
        summary["errors"].append({"row": None, "code": "REFERENCE_CONFLICT", "field": None})
    if summary["error_count"]:
        # Expected business rejection is a completed job with an explicit failed import result.
        batch.status, batch.summary = "FAILED", summary
        return {"batch_id": str(batch.id), "status": "FAILED", "error_code": "IMPORT_REVALIDATION_FAILED"}
    apply_merge(session, batch.dataset_id, batch.kind, mutations, reference_at)
    previous = data_version(session, batch.dataset_id)
    version = previous + bool(mutations)
    if mutations:
        dataset.reference_at = reference_at
        session.add(DatasetVersion(dataset_id=batch.dataset_id, version=version, reason=f"import:{batch.id}"))
        record_change(session, dataset_id=batch.dataset_id, resource_id=batch.id, actor_type="VISITOR",
                      action="DATA_IMPORTED", request_id=UUID(batch.options["request_id"]),
                      previous_version=previous or None, new_version=version)
    summary.update(data_version=version, reference_at=reference_at.isoformat())
    batch.status, batch.summary = "COMPLETED", summary
    return {"batch_id": str(batch.id), "status": "COMPLETED", **summary}
