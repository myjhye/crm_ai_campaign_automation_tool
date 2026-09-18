"""Run with python -m app.workers.runner [--once]."""

import argparse
import logging
import threading

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db.session import Database
from app.services.jobs import LeaseLost, claim_job, fail, finish, renew_lease
from app.workers.handlers import HANDLERS

logger = logging.getLogger(__name__)


def run_once(database, settings, handlers=None):
    handlers = HANDLERS if handlers is None else handlers
    job = claim_job(database.sessions, settings.worker_lease_seconds)
    if job is None:
        return False
    stopped = threading.Event()

    def heartbeat_loop():
        while not stopped.wait(settings.worker_heartbeat_seconds):
            try:
                if not renew_lease(database.sessions, job.id, job.lease_token,
                                   settings.worker_lease_seconds):
                    return
            except SQLAlchemyError:
                logger.warning("Heartbeat failed job_id=%s", job.id)
                return

    pulse = threading.Thread(target=heartbeat_loop, daemon=True)
    pulse.start()
    try:
        handler = handlers.get(job.kind)
        if handler is None:
            raise ValueError("Unsupported job kind")
        with database.sessions.begin() as session:
            result = handler(session, job)
            finish(session, job.id, job.lease_token, result)
    except LeaseLost:
        logger.warning("Lease lost; transaction rolled back job_id=%s", job.id)
    except Exception as exc:
        logger.warning("Job failed job_id=%s type=%s", job.id, type(exc).__name__)
        fail(database.sessions, job, "UNSUPPORTED_JOB" if job.kind not in handlers else "HANDLER_FAILED")
    finally:
        stopped.set()
        pulse.join(timeout=settings.worker_heartbeat_seconds + 4)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process at most one available job")
    args = parser.parse_args()
    settings = Settings()
    if not settings.database_url:
        parser.error("DATABASE_URL is required")
    database = Database(settings.database_url.get_secret_value())
    logging.basicConfig(level=logging.INFO)
    try:
        while True:
            try:
                processed = run_once(database, settings)
            except SQLAlchemyError:
                logger.warning("Database unavailable; retrying")
                if args.once:
                    raise SystemExit(1)
                processed = False
            if args.once:
                break
            if not processed:
                threading.Event().wait(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
