"""Import queries and bulk persistence; never commit here."""
from sqlalchemy import select, func, insert, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.customers import Customer, CustomerChannel, Order, OrderItem, CustomerEvent
from app.models.jobs import ImportBatch, DatasetVersion

def keyed(session, model, dataset_id):
    rows = session.scalars(select(model).where(model.dataset_id == dataset_id)).all()
    if model is OrderItem:
        return {(row.order_id, row.line_id): row for row in rows}
    return {row.external_id: row for row in rows}


def data_version(session, dataset_id):
    return session.scalar(select(func.max(DatasetVersion.version)).where(DatasetVersion.dataset_id == dataset_id)) or 0


def email_channels(session, dataset_id):
    return {c.customer_id: c for c in session.scalars(select(CustomerChannel).where(
        CustomerChannel.dataset_id == dataset_id, CustomerChannel.channel == "EMAIL"))}


def earliest_activity(session, dataset_id, model, timestamp):
    return dict(session.execute(select(model.customer_id, func.min(timestamp)).where(
        model.dataset_id == dataset_id).group_by(model.customer_id)).all())


def customers_and_totals(session, dataset_id, reference_at, customer_ids):
    query = select(Customer).where(Customer.dataset_id == dataset_id)
    aggregate = select(Order.customer_id, func.count(Order.id), func.sum(Order.amount), func.max(Order.purchased_at)).where(
        Order.dataset_id == dataset_id, Order.source == 'UPLOADED', Order.status == "COMPLETED", Order.purchased_at <= reference_at)
    if customer_ids is not None:
        query = query.where(Customer.id.in_(customer_ids))
        aggregate = aggregate.where(Order.customer_id.in_(customer_ids))
    customers = session.scalars(query).all()
    totals = {row[0]: row[1:] for row in session.execute(aggregate.group_by(Order.customer_id))}
    return customers, totals


def persist(session, model, new, changed, channels):
    from uuid import uuid4
    for start in range(0, len(new), 1000):
        session.execute(insert(model), new[start:start + 1000])
    for start in range(0, len(changed), 1000):
        session.execute(update(model), changed[start:start + 1000])
    for start in range(0, len(channels), 1000):
        part = channels[start:start + 1000]
        stmt = pg_insert(CustomerChannel).values(part)
        session.execute(stmt.on_conflict_do_update(constraint="uq_customer_channel", set_={
            k: getattr(stmt.excluded, k) for k in ("consent", "contact", "is_valid", "hard_bounce", "consent_changed_at")}))
        for name in ("PUSH", "SMS"):
            values = [{"id": uuid4(), "dataset_id": c["dataset_id"], "customer_id": c["customer_id"], "channel": name} for c in part]
            session.execute(pg_insert(CustomerChannel).values(values).on_conflict_do_nothing(constraint="uq_customer_channel"))
    session.expire_all()


def get_batch(session, batch_id, lock=False):
    query = select(ImportBatch).where(ImportBatch.id == batch_id)
    return session.scalar(query.with_for_update() if lock else query)
