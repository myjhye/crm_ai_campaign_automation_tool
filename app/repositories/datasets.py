from sqlalchemy import func, select

from app.models.datasets import Dataset
from app.models.customers import Customer, Order, CustomerEvent
from app.schemas.datasets import DatasetResponse


def get(session, dataset_id, *, lock=False):
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.purpose == "ANALYSIS")
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def list_page(session, pagination):
    total = session.scalar(select(func.count()).select_from(Dataset).where(Dataset.purpose == "ANALYSIS"))
    rows = session.scalars(select(Dataset).where(Dataset.purpose == "ANALYSIS").order_by(
        select(Customer.id).where(Customer.dataset_id == Dataset.id).exists().desc(),
        Dataset.created_at.desc(), Dataset.id.desc())
                           .offset(pagination.offset).limit(pagination.page_size)).all()
    return rows, total


def describe(session, rows):
    """Batch counts across the whole dataset, independent of dashboard period."""
    counts = {row.id: {} for row in rows}
    for model, field in ((Customer, "customer_count"), (Order, "order_count"), (CustomerEvent, "event_count")):
        if counts:
            for dataset_id, count in session.execute(select(model.dataset_id, func.count()).where(
                    model.dataset_id.in_(counts)).group_by(model.dataset_id)):
                counts[dataset_id][field] = count
    return [DatasetResponse.model_validate(row).model_copy(update=counts[row.id]) for row in rows]
