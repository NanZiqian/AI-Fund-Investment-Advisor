from datetime import UTC, datetime, timedelta

import pytest

from app.macro import regime
from app.research import Article, ResearchBatch, accept_articles, evidence_summary, store_articles

NOW = datetime(2026, 9, 15, tzinfo=UTC)


def article(**kwargs):
    fields = dict(
        title="Policy",
        source_url="https://www.pbc.gov.cn/news/123",
        published_at=NOW - timedelta(hours=2),
        fact="Test fact",
        interpretation="Explanation",
        uncertainty="Uncertain",
        topic="macro",
        affected_symbols=["012885"],
        impact_score=60,
        confidence=0.8,
    )
    return Article(**(fields | kwargs))


def test_research_rejects_hallucinated_future_and_unknown():
    batch = ResearchBatch(
        articles=[
            article(),
            article(published_at=NOW + timedelta(hours=1)),
            article(affected_symbols=["UNKNOWN"]),
            article(source_url="https://invented.example/"),
        ]
    )
    accepted = accept_articles(batch, {str(article().source_url)}, {"012885"}, NOW)
    assert len(accepted) == 1
    with pytest.raises(ValueError):
        Article(**(article().model_dump() | {"action": "BUY"}))


def test_news_dedup_and_independent_sources(session):
    store_articles(session, [article(), article()], NOW)
    summary = evidence_summary(session, "012885", NOW)
    assert len(summary["ids"]) == 1 and summary["independent_sources"] == 1


def test_macro_missing_stale_and_region_separation():
    assert regime([], NOW)["risk_regime"] == "UNCERTAIN"
    rows = [
        {
            "series": "CPI",
            "date": d,
            "value": v,
            "region": "CN",
            "kind": "inflation",
            "max_age_days": 100,
            "unit": "percent_yoy",
            "source": "https://stats.gov.cn",
        }
        for d, v in [("2026-07-01", "2"), ("2026-08-01", "1")]
    ]
    assert regime(rows, NOW)["inflation_regime"] == "DISINFLATIONARY"
    assert regime(rows, NOW, "US")["inflation_regime"] == "UNCERTAIN"
    assert regime(rows, NOW + timedelta(days=500))["inflation_regime"] == "UNCERTAIN"
