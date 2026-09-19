import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, text
from sqlalchemy.engine import make_url

from app.db.session import Database


@pytest.fixture
def raw_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL *_test database")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Refusing to run DB tests outside a *_test database")
    db = Database(url)
    schema = "test_" + uuid4().hex
    with db.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    db.dispose()

    @event.listens_for(db.engine, "connect")
    def select_schema(connection, record):
        with connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        connection.commit()

    db.test_schema = schema
    try:
        yield db
    finally:
        with db.engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        db.dispose()



@pytest.fixture
def database(raw_database):
    config = Config("alembic.ini")
    with raw_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return raw_database
