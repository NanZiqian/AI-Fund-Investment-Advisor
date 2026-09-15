from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import DateTime, Numeric, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator


def utcnow():
    return datetime.now(UTC)


class AwareTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Timezone required")
            return value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


class Money(TypeDecorator):
    """NUMERIC on Postgres; exact decimal strings on SQLite (never SQLite REAL)."""

    impl = Numeric(24, 8)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(String(64) if dialect.name == "sqlite" else Numeric(24, 8))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("Non-finite money")
        return str(result) if dialect.name == "sqlite" else result

    def process_result_value(self, value, dialect):
        return Decimal(str(value)) if value is not None else None


class Base(DeclarativeBase):
    pass


def make_engine(url):
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

    return engine


def session_factory(url):
    return sessionmaker(make_engine(url), expire_on_commit=False)
