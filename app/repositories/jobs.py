"""Queue queries. The calling service owns every transaction."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update

from app.models.jobs import Job


def claim(session, lease_seconds: int):
    now = session.scalar(select(func.clock_timestamp()))
    # Exhausted leases must not remain RUNNING forever after a final crash.
    session.execute(update(Job).where(
        Job.status == "RUNNING", Job.lease_until <= now, Job.attempt >= Job.max_attempts,
    ).values(status="FAILED", error_code="LEASE_EXHAUSTED", lease_token=None,
             lease_until=None, finished_at=now))
    job = session.scalar(select(Job).where(
        Job.attempt < Job.max_attempts,
        or_(and_(Job.status == "PENDING", Job.available_at <= now),
            and_(Job.status == "RUNNING", Job.lease_until <= now)),
    ).order_by(Job.available_at, Job.id).with_for_update(skip_locked=True).limit(1))
    if job is None:
        return None
    job.status = "RUNNING"
    job.attempt += 1
    job.lease_token = uuid4()
    job.heartbeat_at = now
    job.lease_until = now + timedelta(seconds=lease_seconds)
    job.error_code = None
    job.progress = 0
    session.flush()
    return job


def owned(job_id, token):
    return (Job.id == job_id, Job.status == "RUNNING", Job.lease_token == token,
            Job.lease_until > func.clock_timestamp())


def heartbeat(session, job_id, token, lease_seconds: int):
    return session.execute(update(Job).where(*owned(job_id, token)).values(
        heartbeat_at=func.clock_timestamp(),
        lease_until=func.clock_timestamp() + timedelta(seconds=lease_seconds),
    )).rowcount == 1
