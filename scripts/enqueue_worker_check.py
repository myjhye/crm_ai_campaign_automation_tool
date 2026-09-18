"""Create a diagnostic dataset and job without exposing a public enqueue API."""

import argparse

from app.core.config import Settings
from app.db.session import Database
from app.models.datasets import Dataset
from app.services.jobs import enqueue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0)
    args = parser.parse_args()
    if not 0 <= args.delay <= 60:
        parser.error("delay must be between 0 and 60 seconds")
    settings = Settings()
    if not settings.database_url:
        parser.error("DATABASE_URL is required")
    db = Database(settings.database_url.get_secret_value())
    try:
        with db.sessions.begin() as session:
            dataset = Dataset(name="Worker diagnostic")
            session.add(dataset)
            session.flush()
            job = enqueue(session, dataset_id=dataset.id, kind="system.check", key="diagnostic",
                          payload={"delay_seconds": args.delay})
            job_id = job.id
        print(f"job_id={job_id}")
    finally:
        db.dispose()


if __name__ == "__main__":
    main()
