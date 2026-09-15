import argparse
import csv
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.config import Settings
from app.db import session_factory
from app.db.models import Instrument
from app.portfolio import import_portfolio, parse_csv
from app.schemas import PortfolioImport, PositionInput, ProfileUpdate


def import_universe(session, path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["market"] != "CN":
            raise ValueError("V1 supports only CNY share classes of mainland Chinese public funds")
        valid = PositionInput(
            symbol=row["symbol"],
            name=row["name"],
            market_value=0,
            source=row["source"],
            qdii=row["qdii"],
            category=row["category"],
            share_class=row["share_class"],
        )
        record = session.scalar(select(Instrument).where(Instrument.symbol == valid.symbol))
        if record is None:
            record = Instrument(symbol=valid.symbol, name=valid.name, source=valid.source)
            session.add(record)
        record.category, record.qdii, record.share_class = (
            valid.category,
            valid.qdii,
            valid.share_class,
        )
        record.approved = row["enabled"].lower() == "true"
        record.confirmed = True  # Explicit user-maintained approved universe.
        record.benchmark_symbol = row.get("benchmark_symbol") or None


def main():
    parser = argparse.ArgumentParser(description="China Public Fund Research Assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    imp = sub.add_parser("import-portfolio")
    imp.add_argument("path")
    imp.add_argument("--cash")
    imp.add_argument("--as-of")
    uni = sub.add_parser("import-universe")
    uni.add_argument("path", default="config/fund_universe.csv", nargs="?")
    profile = sub.add_parser("import-profile")
    profile.add_argument("symbol")
    profile.add_argument("path")
    args = parser.parse_args()
    if args.command == "init-db":
        command.upgrade(Config("alembic.ini"), "head")
        print("Database migrated")
        return
    with session_factory(Settings().database_url)() as session:
        if args.command == "import-portfolio":
            path = Path(args.path)
            content = path.read_text(encoding="utf-8-sig")
            payload = (
                PortfolioImport.model_validate_json(content)
                if path.suffix == ".json"
                else parse_csv(content, args.cash, args.as_of)
            )
            snap = import_portfolio(session, payload)
            print(
                f"Imported {len(payload.positions)} positions, "
                f"invested={snap.invested_value}, cash={snap.cash_value}"
            )
        elif args.command == "import-universe":
            import_universe(session, args.path)
        elif args.command == "import-profile":
            record = session.scalar(select(Instrument).where(Instrument.symbol == args.symbol))
            if record is None:
                raise ValueError("Unknown fund code")
            record.profile = ProfileUpdate.model_validate_json(
                Path(args.path).read_text(encoding="utf-8-sig")
            ).model_dump(mode="json", exclude_none=True)
            # Preserve explicit unlimited (null) daily_limit.
            parsed = json.loads(Path(args.path).read_text(encoding="utf-8-sig"))
            if parsed.get("rules"):
                record.profile["rules"]["daily_limit"] = parsed["rules"]["daily_limit"]
        session.commit()


if __name__ == "__main__":
    main()
