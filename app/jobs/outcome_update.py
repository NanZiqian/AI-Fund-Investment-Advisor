import argparse
from datetime import timedelta

from sqlalchemy import select

from app.config import Settings
from app.db import session_factory, utcnow
from app.db.models import Instrument, Recommendation
from app.outcomes import update_outcomes
from app.providers.eastmoney import EastmoneyProvider, save_prices


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    now, failures = utcnow(), []
    with session_factory(Settings().database_url)() as session:
        if not args.offline:
            provider = EastmoneyProvider(session=session, now=now)
            instruments = {i.id: i for i in session.scalars(select(Instrument))}
            tracked = set()
            for rec in session.scalars(select(Recommendation)):
                tracked.add(rec.instrument_id)
                for i in instruments.values():
                    if i.symbol == rec.payload.get("benchmark_symbol"):
                        tracked.add(i.id)
            try:
                for identifier in tracked:
                    i = instruments[identifier]
                    try:
                        bars = provider.get_history(
                            i.symbol, now.date() - timedelta(days=650), now.date()
                        )
                        save_prices(session, i.id, bars)
                    except Exception as exc:
                        failures.append(f"{i.symbol}:{type(exc).__name__}")
            finally:
                provider.close()
        count = update_outcomes(session, now)
        session.commit()
    print(f"Updated {count} outcomes; provider failures: {failures}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
