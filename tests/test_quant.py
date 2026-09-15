import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from app.providers.base import PriceBar
from app.quant import (
    drawdown,
    metrics,
    moving_average,
    period_return,
    portfolio_risk,
    ratios,
    volatility,
)


def bars(values, offset=0):
    return [
        PriceBar(
            date=date(2025, 1, 1) + timedelta(days=n + offset),
            nav=Decimal(str(v)),
            total_return=Decimal(str(v)),
            source="fixture:synthetic",
            retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        for n, v in enumerate(values)
    ]


def test_returns_ma_and_drawdown():
    assert period_return([100, 110, 99], 1) == pytest.approx(-0.1)
    assert period_return([100, 110, 99], 2) == pytest.approx(-0.01)
    assert period_return([100], 5) is None
    assert moving_average([1, 2, 3], 2) == 2.5
    assert drawdown([100, 120, 90, 108]) == -0.25
    with pytest.raises(ValueError):
        period_return([1, float("nan")], 1)


def test_volatility_and_ratios_constant():
    expected = np.std([0.1, -0.1], ddof=1) * math.sqrt(252)
    assert volatility([100, 110, 99], 2) == pytest.approx(expected)
    sharpe, sortino = ratios([1] * 253, 0)
    assert sharpe is None and sortino is None
    assert metrics(bars([1, 1.1]))["return_20d"] is None


def test_sharpe_known_fixture():
    r = np.array([0.01, -0.005] * 126)
    values = np.r_[1, np.cumprod(1 + r)]
    sharpe, _ = ratios(values, 0)
    assert sharpe == pytest.approx(r.mean() / r.std(ddof=1) * math.sqrt(252))


def test_portfolio_correlation_and_risk_contribution():
    values = np.cumprod(1 + np.array([0.01, -0.005] * 130))
    result = portfolio_risk({"a": bars(values), "b": bars(values)}, {"a": 0.4, "b": 0.4})
    assert result["status"] == "OK"
    assert result["correlations"][0]["correlation"] == pytest.approx(1)
    assert result["risk_contributions"]["a"] == pytest.approx(0.5)
    assert portfolio_risk({"a": bars([1] * 100)}, {"a": 0.4, "b": 0.4})["status"] != "OK"


def test_missing_adjustment_never_silently_spliced():
    data = bars([1] * 300)
    data[20].total_return = None
    assert metrics(data)["data_quality"] == "MISSING_ADJUSTMENT"
