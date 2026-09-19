from sqlalchemy import func, select

from app.models.datasets import Dataset


def get(session, dataset_id, *, lock=False):
    statement = select(Dataset).where(Dataset.id == dataset_id)
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def list_page(session, pagination):
    total = session.scalar(select(func.count()).select_from(Dataset))
    rows = session.scalars(select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc())
                           .offset(pagination.offset).limit(pagination.page_size)).all()
    return rows, total
