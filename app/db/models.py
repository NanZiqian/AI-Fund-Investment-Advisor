from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import AwareTime, Base, Money, utcnow


def uid():
    return str(uuid4())


class SystemMeta(Base):
    __tablename__ = "system_meta"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(AwareTime, default=utcnow)


class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    symbol: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str]
    currency: Mapped[str] = mapped_column(default="CNY")
    market: Mapped[str] = mapped_column(default="CN")
    category: Mapped[str] = mapped_column(default="unknown")
    share_class: Mapped[str] = mapped_column(default="unknown")
    qdii: Mapped[bool] = mapped_column(default=False)
    confirmed: Mapped[bool] = mapped_column(default=False)
    approved: Mapped[bool] = mapped_column(default=False)
    benchmark_symbol: Mapped[str | None]
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(AwareTime, default=utcnow)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(primary_key=True, default="personal")
    name: Mapped[str] = mapped_column(default="我的基金账户")
    currency: Mapped[str] = mapped_column(default="CNY")
    cash: Mapped[Decimal | None] = mapped_column(Money)
    as_of: Mapped[datetime | None] = mapped_column(AwareTime)
    source: Mapped[str]


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("account_id", "instrument_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    quantity: Mapped[Decimal | None] = mapped_column(Money)
    market_value: Mapped[Decimal] = mapped_column(Money)
    holding_profit: Mapped[Decimal | None] = mapped_column(Money)
    average_cost: Mapped[Decimal | None] = mapped_column(Money)
    as_of: Mapped[datetime | None] = mapped_column(AwareTime)
    acquired_on: Mapped[Date | None]
    confirmed: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str]


class Snapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(AwareTime, default=utcnow)
    invested_value: Mapped[Decimal] = mapped_column(Money)
    cash_value: Mapped[Decimal | None] = mapped_column(Money)
    total_value: Mapped[Decimal | None] = mapped_column(Money)
    payload: Mapped[dict] = mapped_column(JSON)


class Price(Base):
    __tablename__ = "price_history"
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    date: Mapped[Date] = mapped_column(primary_key=True)
    nav: Mapped[Decimal] = mapped_column(Money)
    total_return: Mapped[Decimal | None] = mapped_column(Money)
    source: Mapped[str]
    retrieved_at: Mapped[datetime] = mapped_column(AwareTime)


class ProviderCache(Base):
    __tablename__ = "provider_cache"
    key: Mapped[str] = mapped_column(primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    retrieved_at: Mapped[datetime] = mapped_column(AwareTime)


class News(Base):
    __tablename__ = "news_items"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    content_hash: Mapped[str] = mapped_column(unique=True)
    source_url: Mapped[str]
    published_at: Mapped[datetime] = mapped_column(AwareTime)
    retrieved_at: Mapped[datetime] = mapped_column(AwareTime)
    payload: Mapped[dict] = mapped_column(JSON)


class MacroObservation(Base):
    __tablename__ = "macro_observations"
    series: Mapped[str] = mapped_column(primary_key=True)
    date: Mapped[Date] = mapped_column(primary_key=True)
    value: Mapped[Decimal] = mapped_column(Money)
    source: Mapped[str]
    retrieved_at: Mapped[datetime] = mapped_column(AwareTime)
    payload: Mapped[dict] = mapped_column(JSON)


class DailyRun(Base):
    __tablename__ = "daily_runs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    run_key: Mapped[str] = mapped_column(unique=True)
    started_at: Mapped[datetime] = mapped_column(AwareTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(AwareTime)
    status: Mapped[str] = mapped_column(default="RUNNING")
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("portfolio_snapshots.id"))
    pipeline_version: Mapped[str] = mapped_column(default="cn-v1.0")
    health: Mapped[dict] = mapped_column(JSON, default=dict)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    telemetry: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None]
    report: Mapped[str | None]


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    daily_run_id: Mapped[str] = mapped_column(ForeignKey("daily_runs.id"))
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    created_at: Mapped[datetime] = mapped_column(AwareTime, default=utcnow)
    action: Mapped[str]
    recommendation_type: Mapped[str]
    proposed_amount: Mapped[Decimal] = mapped_column(Money)
    current_price: Mapped[Decimal | None] = mapped_column(Money)
    payload: Mapped[dict] = mapped_column(JSON)


class Outcome(Base):
    __tablename__ = "recommendation_outcomes"
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id"), primary_key=True
    )
    updated_at: Mapped[datetime] = mapped_column(AwareTime)
    payload: Mapped[dict] = mapped_column(JSON)
