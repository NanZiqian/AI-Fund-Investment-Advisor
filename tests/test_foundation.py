from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, Table, select

from app.config import Settings, save_env_values
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


def test_save_llm_configuration_preserves_other_values(tmp_path):
    template = tmp_path / ".env.example"
    target = tmp_path / ".env"
    template.write_text(
        "DATABASE_URL=sqlite:///data/advisor.db\nOPENAI_API_KEY=\nRESEARCH_ENABLED=false\n",
        encoding="utf-8",
    )
    save_env_values(
        target,
        {"OPENAI_API_KEY": "local-secret", "RESEARCH_ENABLED": "true"},
        template=template,
    )
    saved = target.read_text(encoding="utf-8")
    assert "DATABASE_URL=sqlite:///data/advisor.db" in saved
    assert 'OPENAI_API_KEY="local-secret"' in saved
    assert 'RESEARCH_ENABLED="true"' in saved


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
