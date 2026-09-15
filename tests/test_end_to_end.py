from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.config import Settings
from app.db.models import Instrument, Outcome, Recommendation
from app.jobs.daily import run_daily
from app.portfolio import import_portfolio
from app.providers.base import FundProfile, PriceBar
from app.research import Article, store_articles
from app.schemas import PortfolioImport, PositionInput


def test_complete_deterministic_plan_and_outcome_persist(session, tmp_path, monkeypatch):
    now = datetime(2026, 9, 15, 8, tzinfo=UTC)
    payload = PortfolioImport(
        positions=[
            PositionInput(
                symbol="012885",
                name="测试基金",
                market_value="100",
                confirmed=True,
                as_of=now,
                category="宽基",
                source="fixture:user",
            )
        ],
        cash="9900",
        as_of=now,
        source="fixture:user",
    )
    import_portfolio(session, payload)
    instrument = session.scalar(select(Instrument))
    instrument.profile = {
        "source": "https://issuer.example/profile",
        "as_of": now.isoformat(),
        "diversification_score": 100,
        "liquidity_score": 100,
        "valuation_score": 100,
        "tracking_score": 100,
        "expense_ratio": "0.001",
        "rules": {
            "source": "https://issuer.example/rules",
            "as_of": now.isoformat(),
            "subscription_status": "OPEN",
            "daily_limit": "300",
            "minimum_subscription": "1",
        },
    }
    for domain in ("stats.gov.cn", "pbc.gov.cn"):
        store_articles(
            session,
            [
                Article(
                    title="固定测试新闻",
                    source_url=f"https://{domain}/test",
                    published_at=now - timedelta(hours=1),
                    fact="固定测试事实",
                    interpretation="正面",
                    uncertainty="测试",
                    topic="宽基",
                    affected_symbols=["012885"],
                    impact_score=80,
                    confidence=0.9,
                )
            ],
            now,
        )
    session.commit()

    class Provider:
        requests = 1

        def get_history(self, symbol, start, end):
            return [
                PriceBar(
                    date=now.date() - timedelta(days=300 - n),
                    nav=Decimal("1") + Decimal(n) / 1000,
                    total_return=Decimal("1") + Decimal(n) / 1000,
                    source="fixture:synthetic",
                    retrieved_at=now,
                )
                for n in range(301)
            ]

        def get_fund_profile(self, symbol):
            return FundProfile(
                symbol=symbol, name="测试基金", source="fixture:synthetic", retrieved_at=now
            )

    monkeypatch.setattr("app.jobs.daily.fetch_fred", lambda *_: ([], ["NOT_CONFIGURED"]))
    run = run_daily(
        Settings(report_dir=tmp_path, research_enabled=False),
        provider=Provider(),
        session=session,
        now=now,
    )
    assert run.status == "PARTIAL"  # Missing macro/LLM are explicitly degraded.
    rec = session.scalar(select(Recommendation))
    assert rec.action == "BUY" and rec.proposed_amount == Decimal("300.00")
    assert rec.payload["risk_gate_status"] == "RESIZED"
    assert run.inputs["signals"] and run.inputs["histories"]
    outcome = session.get(Outcome, rec.id)
    assert outcome.payload["return_1d"] is None
    assert run.health["outcomes"] == "OK"
    from app.replay import replay

    assert replay(session, run.id)["verified"]
