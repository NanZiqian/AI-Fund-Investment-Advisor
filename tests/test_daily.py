from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.config import Settings
from app.db.models import Recommendation
from app.jobs.daily import run_daily
from app.portfolio import import_portfolio
from app.schemas import PortfolioImport, PositionInput


def test_offline_real_holdings_never_fake_nav_or_cash(session, tmp_path):
    import_portfolio(
        session,
        PortfolioImport(
            positions=[
                PositionInput(
                    symbol="012885",
                    name="光伏A",
                    market_value=Decimal("783.67"),
                    source="user:screenshot",
                )
            ],
            source="user:screenshot",
        ),
    )
    session.commit()
    settings = Settings(report_dir=tmp_path)
    now = datetime(2026, 9, 15, 8, tzinfo=UTC)
    run = run_daily(settings, offline=True, now=now, session=session)
    assert run.status == "PARTIAL"
    assert "783.67" in run.report and "现金" in run.report
    rec = session.scalar(select(Recommendation))
    assert rec.action == "WATCH" and rec.current_price is None and rec.proposed_amount == 0
    assert run.inputs["portfolio"]["cash"] is None
    assert run_daily(settings, offline=True, now=now, session=session).id == run.id
    assert len(list(session.scalars(select(Recommendation)))) == 1


def test_provider_failure_keeps_report(session, tmp_path):
    class BrokenProvider:
        def get_history(self, *args):
            raise TimeoutError("private token must not be stored")

    import_portfolio(
        session,
        PortfolioImport(
            positions=[PositionInput(symbol="012885", name="光伏A", market_value=1, source="test")],
            source="test",
        ),
    )
    session.commit()
    run = run_daily(Settings(report_dir=tmp_path), provider=BrokenProvider(), session=session)
    assert run.status == "PARTIAL" and "private token" not in str(run.health)
    assert "TimeoutError" in run.report
