"""Audit metadata only: never accept arbitrary request bodies or contact values."""
from uuid import UUID

from app.models.datasets import AuditLog
from app.schemas.audit import ActorType


def record_change(session, *, dataset_id: UUID, resource_id: UUID,
                  actor_type: ActorType, action: str, request_id: UUID | None,
                  previous_version: int | None, new_version: int | None):
    entry = AuditLog(dataset_id=dataset_id, resource_id=resource_id, actor_type=actor_type,
                     action=action, request_id=request_id, previous_version=previous_version,
                     new_version=new_version, details={})
    session.add(entry)
    session.flush()
    return entry
