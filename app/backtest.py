"""Price-only baseline; no historical LLM/news replay and no assumed evidence."""

import argparse
import json
from decimal import Decimal

from sqlalchemy import select

from app.config import Settings
from app.db import session_factory
from app.db.models import Instrument
from app.providers.eastmoney import load_prices
from app.quant import moving_average, period_return


def simulate(bars, initial_cash=Decimal("10000"), fee_rate=Decimal("0.001"), settings=None):
    settings = settings or Settings()
    cash, units, pending = initial_cash, Decimal(0), None
    events, curve = [], []
    for n, bar in enumerate(bars):
        price = bar.total_return  # normalized total return index; units are synthetic
        if price is None:
            raise ValueError("Complete total return history required")
        if pending is not None:
            total = cash + units * price
            if pending == "BUY":
                amount = min(
                    total * settings.max_new_position,
                    max(Decimal(0), cash - total * settings.min_cash_ratio) / (1 + fee_rate),
                    max(Decimal(0), total * settings.max_position - units * price)
                    / (1 + settings.max_position * fee_rate),
                )
                amount = min(amount, cash / (1 + fee_rate))
                if amount >= settings.min_trade_amount:
                    cash -= amount * (1 + fee_rate)
                    units += amount / price
                    events.append({"date": str(bar.date), "action": "BUY", "amount": str(amount)})
            elif units:
                amount = units * price
                cash += amount * (1 - fee_rate)
                units = Decimal(0)
                events.append({"date": str(bar.date), "action": "REDUCE", "amount": str(amount)})
        pending = None
        if n >= 60:
            values = [b.total_return for b in bars[: n + 1]]
            ma, momentum = moving_average(values, 50), period_return(values, 20)
            if float(price) > ma and momentum > 0:
                pending = "BUY"
            elif float(price) < ma and momentum < 0:
                pending = "REDUCE"
        curve.append({"date": str(bar.date), "value": str(cash + units * price)})
    return {
        "method": "quant-only next-observation execution; synthetic total-return units",
        "fee_assumption": str(fee_rate),
        "initial_cash": str(initial_cash),
        "final_value": curve[-1]["value"] if curve else str(initial_cash),
        "events": events,
        "curve": curve,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol")
    args = parser.parse_args()
    with session_factory(Settings().database_url)() as session:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == args.symbol))
        if instrument is None:
            raise ValueError("Unknown fund")
        bars = load_prices(session, instrument.id)
        if len(bars) < 61:
            raise ValueError("Insufficient history")
        print(json.dumps(simulate(bars), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
