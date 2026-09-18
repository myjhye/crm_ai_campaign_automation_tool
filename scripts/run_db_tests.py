"""Run tests in isolated schemas of a dedicated *_test PostgreSQL database."""

import argparse
import os
import subprocess
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true", help="Create the test database if missing")
    args = parser.parse_args()
    settings = Settings()
    explicit_url = os.environ.get("TEST_DATABASE_URL")
    if explicit_url:
        target = make_url(explicit_url)
    elif settings.database_url:
        source = make_url(settings.database_url.get_secret_value())
        target = source.set(database=(source.database or "growthpilot") + "_test")
    else:
        parser.error("DATABASE_URL or TEST_DATABASE_URL is required")
    if target.drivername != "postgresql+psycopg" or not (target.database or "").endswith("_test"):
        parser.error("Tests require a postgresql+psycopg URL ending in a *_test database")
    if args.create:
        admin_url = target.set(drivername="postgresql", database="postgres")
        with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target.database,)).fetchone()
            if not exists:
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target.database)))
    env = os.environ.copy()
    env["TEST_DATABASE_URL"] = target.render_as_string(hide_password=False)
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q"], env=env))


if __name__ == "__main__":
    main()
