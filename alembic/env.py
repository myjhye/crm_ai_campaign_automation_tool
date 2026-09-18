from alembic import context

from app.core.config import Settings
from app.db.base import Base
from app.db.session import Database
import app.models  # noqa: F401

config = context.config
target_metadata = Base.metadata


def configure(connection=None, url=None):
    context.configure(
        connection=connection, url=url, target_metadata=target_metadata,
        compare_type=True, literal_binds=connection is None,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    settings = Settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    configure(url=settings.database_url.get_secret_value())
elif config.attributes.get("connection") is not None:
    configure(connection=config.attributes["connection"])
else:
    settings = Settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    db = Database(settings.database_url.get_secret_value())
    try:
        with db.engine.connect() as connection:
            configure(connection=connection)
    finally:
        db.dispose()
