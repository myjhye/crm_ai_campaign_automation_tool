from sqlalchemy import func, select

from app.models.datasets import AuditLog


def list_page(session, filters):
    conditions = [getattr(AuditLog, name) == getattr(filters, name)
                  for name in ("dataset_id", "resource_id", "actor_type", "action")
                  if getattr(filters, name) is not None]
    total = session.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    rows = session.scalars(select(AuditLog).where(*conditions)
                           .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                           .offset(filters.offset).limit(filters.page_size)).all()
    return rows, total
