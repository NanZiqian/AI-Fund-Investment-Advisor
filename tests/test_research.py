from datetime import UTC, datetime, timedelta

import httpx
import pytest
from openai import OpenAI

from app.config import Settings
from app.macro import regime
from app.research import (
    Article,
    ResearchBatch,
    ResearchClient,
    accept_articles,
    ensure_openai_json_parser,
    evidence_summary,
    store_articles,
)

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


def test_stdlib_json_fallback_replaces_unloadable_jiter(monkeypatch):
    import builtins
    import sys

    real_import = builtins.__import__

    def broken_jiter(name, *args, **kwargs):
        if name == "jiter":
            raise ImportError("DLL load failed")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "jiter", raising=False)
    monkeypatch.setattr(builtins, "__import__", broken_jiter)
    assert ensure_openai_json_parser() is True
    assert sys.modules["jiter"].from_json(b'{"ok":true}') == {"ok": True}
    monkeypatch.setattr(builtins, "__import__", real_import)
    assert ensure_openai_json_parser() is True

    payload = {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "model": "test-model",
        "status": "completed",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"articles":[]}',
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }

    def handler(request):
        return httpx.Response(200, json=payload, request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OpenAI(
        api_key="test", base_url="https://example.invalid/v1", http_client=http_client
    )
    researcher = ResearchClient(Settings(openai_api_key="test"), client=client)
    parsed, _ = researcher.parse("test-model", ResearchBatch, "test")
    assert parsed == ResearchBatch(articles=[])
    http_client.close()
