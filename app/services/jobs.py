import hashlib
import json
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import AppError
from app.models.jobs import Job
from app.repositories import jobs as repository


class LeaseLost(Exception):
    pass


def enqueue(session, *, dataset_id, kind: str, key: str, payload: dict, max_attempts=3):
    """Participates in the caller's business transaction; never commits here."""
    if not kind or len(kind) > 100 or not key or len(key) > 200 or max_attempts < 1:
        raise ValueError("Invalid job metadata")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                      allow_nan=False).encode()).hexdigest()
    job_id = session.scalar(insert(Job).values(
        dataset_id=dataset_id, kind=kind, idempotency_key=key, payload=payload,
        payload_hash=digest, max_attempts=max_attempts,
    ).on_conflict_do_nothing(constraint="uq_job_idempotency").returning(Job.id))
    if job_id:
        return session.get(Job, job_id)
    existing = session.scalar(select(Job).where(
        Job.dataset_id == dataset_id, Job.kind == kind, Job.idempotency_key == key))
    if existing.payload_hash != digest or existing.max_attempts != max_attempts:
        raise AppError("IDEMPOTENCY_CONFLICT", "같은 키에 다른 작업을 사용할 수 없습니다.")
    return existing


def claim_job(sessions, lease_seconds):
    with sessions.begin() as session:
        return repository.claim(session, lease_seconds)


def renew_lease(sessions, job_id, token, lease_seconds):
    with sessions.begin() as session:
        return repository.heartbeat(session, job_id, token, lease_seconds)


def finish(session, job_id, token, result):
    """Fenced completion in the SAME transaction as handler database effects."""
    changed = session.execute(update(Job).where(*repository.owned(job_id, token)).values(
        status="SUCCEEDED", result=result, progress=100, finished_at=func.clock_timestamp(),
        lease_token=None, lease_until=None, error_code=None,
    )).rowcount
    if changed != 1:
        raise LeaseLost()


def fail(sessions, job, error_code):
    with sessions.begin() as session:
        terminal = job.attempt >= job.max_attempts
        session.execute(update(Job).where(*repository.owned(job.id, job.lease_token)).values(
            status="FAILED" if terminal else "PENDING", error_code=error_code,
            lease_token=None, lease_until=None,
            finished_at=func.clock_timestamp() if terminal else None,
            available_at=func.clock_timestamp() + timedelta(seconds=min(2 ** job.attempt, 60)),
        ))
