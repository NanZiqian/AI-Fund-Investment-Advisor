from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtest import simulate
from app.outcomes import forward_outcome
from app.providers.base import PriceBar


def data(values):
    return [
        PriceBar(
            date=date(2026, 1, 1) + timedelta(days=n),
            nav=Decimal(str(v)),
            total_return=Decimal(str(v)),
            source="fixture:synthetic",
            retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        for n, v in enumerate(values)
    ]


def test_outcome_uses_future_entry_and_leaves_unmatured_null():
    values = data([100, 200, 220, 240, 260, 280, 300])
    outcome = forward_outcome(
        values, datetime(2026, 1, 1, 8, tzinfo=UTC), now=datetime(2026, 9, 1, tzinfo=UTC)
    )
    assert outcome["entry_date"] == "2026-01-02"
    assert outcome["return_1d"] == pytest.approx(0.1)
    assert outcome["return_5d"] == pytest.approx(0.5)
    assert outcome["return_20d"] is None
    assert outcome["benchmark_return_5d"] is None


def test_benchmark_requires_same_dates_and_60d_matures():
    values = data([100 + n for n in range(63)])
    outcome = forward_outcome(
        values, datetime(2026, 1, 1, tzinfo=UTC), values, now=datetime(2026, 9, 1, tzinfo=UTC)
    )
    assert outcome["excess_return_60d"] == 0
    assert outcome["return_60d"] == pytest.approx(161 / 101 - 1)
    missing = forward_outcome(values, datetime(2026, 1, 1, tzinfo=UTC), values[2:])
    assert missing["benchmark_return_5d"] is None


def test_backtest_future_changes_cannot_change_past_trades():
    original = data([100 + n for n in range(120)])
    a = simulate(original)
    modified = data([100 + n if n < 100 else 1 for n in range(120)])
    b = simulate(modified)
    cut = str(original[99].date)
    assert [x for x in a["events"] if x["date"] <= cut] == [
        x for x in b["events"] if x["date"] <= cut
    ]
    assert a["events"][0]["date"] > str(original[60].date)
