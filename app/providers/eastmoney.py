import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

from app.db import utcnow
from app.db.models import Price, ProviderCache
from app.providers.base import FundProfile, PriceBar, ProviderError, validate_history
from app.providers.http import request


def extract_json(script, name):
    match = re.search(r"\bvar\s+" + re.escape(name) + r"\s*=\s*", script)
    if not match:
        raise ProviderError(f"Missing provider field: {name}")
    try:
        value, _ = json.JSONDecoder(parse_float=Decimal).raw_decode(script[match.end() :])
        return value
    except (ValueError, TypeError):
        raise ProviderError(f"Invalid JSON field: {name}") from None


class EastmoneyProvider:
    """The same public source used by AKShare; parses JSON without executing remote JS."""

    def __init__(self, session=None, client=None, now=None):
        self.session = session
        self.client = client or httpx.Client(headers={"User-Agent": "Mozilla/5.0"})
        self.owns_client = client is None
        self.now = now or utcnow()
        self.memory = {}
        self.requests = 0

    def close(self):
        if self.owns_client:
            self.client.close()

    def _data(self, symbol):
        if not re.fullmatch(r"\d{6}", symbol):
            raise ProviderError("A six-digit fund code is required")
        if symbol in self.memory:
            return self.memory[symbol]
        key = f"eastmoney:{symbol}"
        cached = self.session.get(ProviderCache, key) if self.session else None
        if cached and 0 <= (self.now - cached.retrieved_at).total_seconds() < 3600:
            result = (cached.payload["text"], cached.retrieved_at)
        else:
            url = f"https://fund.eastmoney.com/pingzhongdata/{symbol}.js"
            response = request(
                self.client, "GET", url, provider="eastmoney", operation="fund_data", symbol=symbol
            )
            self.requests += 1
            script = response.text
            if len(script) > 10_000_000:
                raise ProviderError("Provider response too large")
            if str(extract_json(script, "fS_code")) != symbol:
                raise ProviderError("Fund code mismatch")
            extract_json(script, "Data_netWorthTrend")
            result = (script, self.now)
            if self.session:
                if not cached:
                    cached = ProviderCache(key=key)
                    self.session.add(cached)
                cached.payload = {"text": script}
                cached.retrieved_at = self.now
        self.memory[symbol] = result
        return result

    def get_fund_profile(self, symbol):
        script, retrieved_at = self._data(symbol)
        return FundProfile(
            symbol=symbol,
            name=extract_json(script, "fS_name"),
            source=f"https://fund.eastmoney.com/{symbol}.html",
            retrieved_at=retrieved_at,
        )

    def get_history(self, symbol, start: date, end: date):
        script, retrieved_at = self._data(symbol)
        records = extract_json(script, "Data_netWorthTrend")
        bars = []
        total = Decimal(1)
        prior = None
        for index, row in enumerate(records):
            day = (
                datetime.fromtimestamp(int(row["x"]) / 1000, UTC)
                .astimezone(ZoneInfo("Asia/Shanghai"))
                .date()
            )
            if prior and day <= prior:
                raise ProviderError("Duplicate or unsorted NAV dates")
            prior = day
            growth = row.get("equityReturn")
            if index:
                if growth is None or growth == "" or total is None:
                    total = None
                else:
                    total *= 1 + Decimal(str(growth)) / 100
            if start <= day <= end:
                bars.append(
                    PriceBar(
                        date=day,
                        nav=Decimal(str(row["y"])),
                        total_return=total,
                        source=f"https://fund.eastmoney.com/pingzhongdata/{symbol}.js",
                        retrieved_at=retrieved_at,
                    )
                )
        return validate_history(bars, end)


def save_prices(session, instrument_id, bars):
    for bar in bars:
        row = session.get(Price, (instrument_id, bar.date))
        if row is None:
            row = Price(instrument_id=instrument_id, date=bar.date)
            session.add(row)
        for key in ("nav", "total_return", "source", "retrieved_at"):
            setattr(row, key, getattr(bar, key))
    session.flush()


def load_prices(session, instrument_id, end=None):
    query = select(Price).where(Price.instrument_id == instrument_id)
    if end:
        query = query.where(Price.date <= end)
    return [
        PriceBar(
            date=p.date,
            nav=p.nav,
            total_return=p.total_return,
            source=p.source,
            retrieved_at=p.retrieved_at,
        )
        for p in session.scalars(query.order_by(Price.date))
    ]
