from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


class Database:
    def __init__(self, url: str):
        parsed = make_url(url)
        if parsed.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        self.engine = create_engine(
            parsed, pool_pre_ping=True, hide_parameters=True,
            connect_args={"connect_timeout": 3, "options":
                          parsed.query.get("options", "") + " -c timezone=UTC -c statement_timeout=15000"},
        )
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def dispose(self):
        self.engine.dispose()
