from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, Table, select

from app.config import Settings
from app.db import Base, Money, make_engine
from app.main import create_app


def test_health(tmp_path):
    client = TestClient(create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db")))
    assert client.get("/health").json()["execution"] == "disabled"


def test_settings_no_secrets():
    settings = Settings(openai_api_key="secret")
    assert "secret" not in str(settings.public())
    with pytest.raises(ValueError):
        Settings(min_cash_ratio=2)


def test_money_exact():
    engine = make_engine("sqlite:///:memory:")
    table = Table(
        "money_test",
        Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("amount", Money),
        extend_existing=True,
    )
    table.create(engine)
    with engine.begin() as conn:
        value = Decimal("1234567890.12345678")
        conn.execute(table.insert().values(amount=value))
        assert conn.execute(select(table.c.amount)).scalar_one() == value
    Base.metadata.remove(table)
