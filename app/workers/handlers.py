"""Handlers only perform transactional DB effects; no commits or external sends."""

import time

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.dialects.postgresql import insert

from app.models.datasets import AuditLog
from app.services.imports import import_job
from app.services.simulations import simulation_job


class CheckPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delay_seconds: float = Field(default=0, ge=0, le=60)


def system_check(session, job):
    payload = CheckPayload.model_validate(job.payload)
    if payload.delay_seconds:
        time.sleep(payload.delay_seconds)
    session.execute(insert(AuditLog).values(
        dataset_id=job.dataset_id, actor_type="SYSTEM", resource_id=job.id,
        action="WORKER_CHECK", event_key=f"job:{job.id}", details={"job_id": str(job.id)},
    ).on_conflict_do_nothing(constraint="uq_audit_event_key"))
    return {"message": "worker check completed"}


HANDLERS = {"system.check": system_check, "data.import": import_job, "campaign.simulate": simulation_job}
