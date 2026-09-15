import csv
import io
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select

from app.db import utcnow
from app.db.models import Account, Instrument, Position, Snapshot
from app.schemas import PortfolioImport, PositionInput

CENT = Decimal("0.01")


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_csv(content: str, cash=None, as_of=None):
    rows = []
    for row in csv.DictReader(io.StringIO(content.lstrip("\ufeff"))):
        rows.append(PositionInput.model_validate({k: v for k, v in row.items() if v != ""}))
    return PortfolioImport(positions=rows, cash=cash, as_of=as_of, source="user:csv")


def import_portfolio(session, payload: PortfolioImport):
    account = session.get(Account, "personal")
    if account is None:
        account = Account(id="personal", source=payload.source)
        session.add(account)
    account.cash = payload.cash
    account.as_of = payload.as_of
    account.source = payload.source
    session.flush()
    if payload.mode == "replace":
        session.execute(delete(Position).where(Position.account_id == account.id))
    for row in payload.positions:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == row.symbol))
        if instrument is None:
            instrument = Instrument(symbol=row.symbol, name=row.name, source=row.source)
            session.add(instrument)
        for key in ("name", "category", "share_class", "qdii", "confirmed"):
            setattr(instrument, key, getattr(row, key))
        session.flush()
        position = session.scalar(
            select(Position).where(
                Position.account_id == account.id, Position.instrument_id == instrument.id
            )
        )
        if position is None:
            position = Position(account_id=account.id, instrument_id=instrument.id)
            session.add(position)
        for key in (
            "quantity",
            "market_value",
            "holding_profit",
            "average_cost",
            "as_of",
            "acquired_on",
            "confirmed",
            "source",
        ):
            setattr(position, key, getattr(row, key))
    session.flush()
    return snapshot(session)


def portfolio_view(session):
    account = session.get(Account, "personal")
    if account is None:
        return {
            "positions": [],
            "invested": "0.00",
            "cash": None,
            "total": None,
            "as_of": None,
            "cash_ratio": None,
            "warnings": ["尚未导入持仓"],
        }
    rows = []
    for p, i in session.execute(
        select(Position, Instrument)
        .join(Instrument)
        .where(Position.account_id == account.id)
        .order_by(Instrument.symbol)
    ):
        rows.append(
            {
                "instrument_id": i.id,
                "symbol": i.symbol,
                "name": i.name,
                "quantity": str(p.quantity) if p.quantity is not None else None,
                "market_value": str(p.market_value),
                "holding_profit": str(p.holding_profit) if p.holding_profit is not None else None,
                "average_cost": str(p.average_cost) if p.average_cost is not None else None,
                "as_of": p.as_of.isoformat() if p.as_of else None,
                "acquired_on": p.acquired_on.isoformat() if p.acquired_on else None,
                "confirmed": p.confirmed and i.confirmed,
                "source": p.source,
                "category": i.category,
                "share_class": i.share_class,
                "qdii": i.qdii,
            }
        )
    invested = sum((Decimal(p["market_value"]) for p in rows), Decimal(0))
    total = invested + account.cash if account.cash is not None else None
    for row in rows:
        row["weight"] = str(Decimal(row["market_value"]) / total) if total else None
        row["invested_weight"] = str(Decimal(row["market_value"]) / invested) if invested else "0"
    warnings = []
    if account.cash is None:
        warnings.append("现金未知：总资产、现金比率及加仓预算不可计算")
    if any(not p["confirmed"] for p in rows):
        warnings.append("存在待确认持仓；截图金额不是实时资产估值")
    return {
        "positions": rows,
        "invested": str(money(invested)),
        "cash": str(account.cash) if account.cash is not None else None,
        "total": str(money(total)) if total is not None else None,
        "cash_ratio": str(account.cash / total) if total else None,
        "as_of": account.as_of.isoformat() if account.as_of else None,
        "warnings": warnings,
    }


def snapshot(session):
    view = portfolio_view(session)
    record = Snapshot(
        account_id="personal",
        created_at=utcnow(),
        invested_value=Decimal(view["invested"]),
        cash_value=Decimal(view["cash"]) if view["cash"] is not None else None,
        total_value=Decimal(view["total"]) if view["total"] is not None else None,
        payload=view,
    )
    session.add(record)
    session.flush()
    return record
