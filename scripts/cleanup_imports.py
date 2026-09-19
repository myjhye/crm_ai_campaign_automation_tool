"""Remove expired staging bytes, preserving summaries and active jobs."""
from sqlalchemy import select, func
from app.core.config import Settings
from app.db.session import Database
from app.models.jobs import ImportBatch, Job


def cleanup(session):
    batches = session.scalars(select(ImportBatch).where(
        ImportBatch.expires_at <= func.clock_timestamp(), ImportBatch.content.is_not(None)
    ).with_for_update(skip_locked=True)).all()
    removed = 0
    for batch in batches:
        if batch.job_id:
            job = session.get(Job, batch.job_id)
            if job.status in ("PENDING", "RUNNING"):
                continue
            if job.status == "FAILED" and batch.status == "QUEUED":
                batch.status = "FAILED"
        batch.content = None
        removed += 1
    return removed


def main():
    settings = Settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL required")
    db = Database(settings.database_url.get_secret_value())
    try:
        with db.sessions.begin() as session:
            print(f"Expired staging payloads removed: {cleanup(session)}")
    finally:
        db.dispose()

if __name__ == "__main__":
    main()
