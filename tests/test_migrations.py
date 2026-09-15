from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db import make_engine


def test_migrations_upgrade_downgrade_roundtrip(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/migration.db"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = make_engine(url)
    assert "recommendation_outcomes" in inspect(engine).get_table_names()
    command.downgrade(config, "0002")
    assert "recommendation_outcomes" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    engine.dispose()
