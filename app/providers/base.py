from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from pydantic import AwareDatetime, Field

from app.schemas import StrictModel


class PriceBar(StrictModel):
    date: date
    nav: Decimal = Field(gt=0, allow_inf_nan=False)
    total_return: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    source: str = Field(min_length=1)
    retrieved_at: AwareDatetime


class FundProfile(StrictModel):
    symbol: str
    name: str
    source: str
    retrieved_at: AwareDatetime


class MarketDataProvider(Protocol):
    def get_history(self, symbol: str, start: date, end: date) -> list[PriceBar]: ...
    def get_fund_profile(self, symbol: str) -> FundProfile: ...


class ProviderError(RuntimeError):
    """Safe error text, no credentials or raw HTTP request string."""


def validate_history(bars: list[PriceBar], end: date):
    dates = [bar.date for bar in bars]
    if not dates or dates != sorted(set(dates)) or dates[-1] > end:
        raise ProviderError("Invalid, duplicate, unsorted or future NAV dates")
    return bars


def elapsed_business_days(start: date, end: date, holidays=frozenset()):
    from datetime import timedelta

    return sum(
        1
        for n in range(1, max(0, (end - start).days) + 1)
        if (day := start + timedelta(days=n)).weekday() < 5 and day not in holidays
    )


def is_fresh(nav_date: date, now: datetime, qdii=False, holidays=frozenset()):
    from zoneinfo import ZoneInfo

    local = now.astimezone(ZoneInfo("Asia/Shanghai"))
    # After 23:00, domestic funds should disclose today's NAV; QDII allow 2 sessions.
    allowance = (2 if qdii else 0) + (1 if local.hour < 23 else 0)
    return (
        nav_date <= local.date()
        and elapsed_business_days(nav_date, local.date(), holidays) <= allowance
    )
