from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from app.config import Settings
from app.recommendations import recommend
from app.risk import RiskContext, RiskGate
from app.signals import Signal

NOW = datetime(2026, 9, 15, 8, tzinfo=UTC)


def context(**changes):
    fields = dict(
        total=D(10000),
        cash=D(4000),
        current_value=D(1000),
        sector_value=D(1000),
        portfolio_confirmed=True,
        price=D(1),
        fresh=True,
        coverage=1,
        confidence=0.9,
        independent_sources=2,
        category="宽基",
        portfolio_volatility=0.15,
        acquired_on=date(2025, 1, 1),
        now=NOW,
        rules={
            "as_of": NOW.isoformat(),
            "source": "https://issuer.example/rules",
            "subscription_status": "OPEN",
            "daily_limit": None,
            "redemption_status": "OPEN",
            "redemption_fee_rate": "0",
            "minimum_holding_days": 7,
        },
    )
    return RiskContext(**(fields | changes))


@pytest.mark.parametrize(
    "changes,rule",
    [
        ({"cash": D(1000)}, "MIN_CASH_BREACH"),
        ({"current_value": D(2200)}, "MAX_POSITION_BREACH"),
        ({"sector_value": D(3500)}, "MAX_SECTOR_BREACH"),
        ({"confidence": 0.2}, "LOW_CONFIDENCE"),
        ({"fresh": False}, "DATA_STALE"),
        ({"price": None}, "MISSING_PRICE"),
        ({"coverage": 0.4}, "INSUFFICIENT_DATA"),
        ({"independent_sources": 1}, "INSUFFICIENT_EVIDENCE"),
        ({"correlation": 0.99}, "EXCESS_CORRELATION"),
        ({"conflicting": True}, "CONFLICTING_SIGNALS"),
        ({"portfolio_volatility": 0.6}, "PORTFOLIO_RISK_TOO_HIGH"),
    ],
)
def test_risk_veto(changes, rule):
    result = RiskGate(Settings()).validate("BUY", D(500), context(**changes))
    assert result.action == "WATCH" and result.amount == 0
    assert rule in result.rules


def test_resize_and_batch_budget_no_use_of_redemptions():
    gate = RiskGate(Settings())
    first = gate.validate("BUY", D(3000), context())
    assert first.amount == 1000 and first.status == "RESIZED"
    gate.validate("REDUCE", D(1000), context())
    assert gate.validate("BUY", D(500), context()).action == "WATCH"


def test_unknown_cash_rules_and_holding_period():
    assert RiskGate(Settings()).validate("BUY", D(500), context(cash=None)).action == "WATCH"
    assert RiskGate(Settings()).validate("BUY", D(500), context(rules={})).action == "WATCH"
    assert (
        RiskGate(Settings()).validate("REDUCE", D(500), context(acquired_on=None)).action == "WATCH"
    )


def test_concentrated_holding_reduce_through_gate():
    signal = Signal("STRATEGIC", 75, 1, {})
    ev = {"ids": ["e1", "e2"], "quality": 1, "model_confidence": 0.9, "independent_sources": 2}
    result = recommend(
        "012885",
        "测试",
        signal,
        signal,
        context(current_value=D(3000)),
        ev,
        RiskGate(Settings()),
        held=True,
    )
    assert result["action"] == "REDUCE" and D(result["proposed_amount"]) == 1000
    assert D(result["target_weight"]) == D(".2")


def test_new_position_cap_and_cent_rounding():
    result = RiskGate(Settings()).validate("BUY", D("700.999"), context(current_value=D(0)))
    assert result.amount == D("500.00")


def test_nan_confidence_and_unknown_holding_rule():
    gate = RiskGate(Settings())
    assert gate.validate("BUY", D(100), context(confidence=float("nan"))).action == "WATCH"
    c = context()
    c.rules["minimum_holding_days"] = None
    assert "HOLDING_RULE_UNKNOWN" in gate.validate("REDUCE", D(100), c).rules
