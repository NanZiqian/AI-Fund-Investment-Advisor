from decimal import Decimal

import pytest

from app.portfolio import import_portfolio, parse_csv, portfolio_view
from app.schemas import PortfolioImport, PositionInput


def test_snapshot_exact_unknown_cash_and_idempotent_import(session):
    payload = parse_csv(
        "symbol,name,market_value,source\n012885,Solar Fund A,783.67,user:screenshot"
    )
    first = import_portfolio(session, payload)
    import_portfolio(session, payload)
    view = portfolio_view(session)
    assert len(view["positions"]) == 1
    assert first.invested_value == Decimal("783.67")
    assert first.total_value is None
    assert view["positions"][0]["quantity"] is None
    assert view["positions"][0]["symbol"] == "012885"


def test_validation_and_csv_leading_zero():
    with pytest.raises(ValueError):
        PositionInput(symbol="1234", name="bad", market_value=1, source="test")
    with pytest.raises(ValueError):
        PositionInput(symbol="001234", name="bad", market_value="NaN", source="test")
    with pytest.raises(ValueError):
        PortfolioImport(positions=[], cash=0, source="test")
    with pytest.raises(ValueError):
        parse_csv("symbol,name,market_value,source\n001234,A,1,test\n001234,A,2,test")


def test_known_zero_cash(session):
    payload = parse_csv(
        "symbol,name,market_value,source\n012885,Solar Fund A,100,test",
        cash="0",
        as_of="2026-09-15T10:00:00+08:00",
    )
    import_portfolio(session, payload)
    assert portfolio_view(session)["total"] == "100.00"
    assert portfolio_view(session)["cash_ratio"] == "0"
