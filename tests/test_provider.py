from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest

from app.providers.base import ProviderError, is_fresh
from app.providers.eastmoney import EastmoneyProvider, extract_json

SCRIPT = """var fS_code = "012885"; var fS_name = "测试A";
var Data_netWorthTrend = [
{"x":1789401600000,"y":1.0,"equityReturn":0},
{"x":1789488000000,"y":0.95,"equityReturn":1.0}];"""


def test_provider_adjusts_distribution_and_caches(session):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text=SCRIPT)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = EastmoneyProvider(session, client)
    bars = provider.get_history("012885", date(2026, 1, 1), date(2026, 12, 31))
    assert bars[1].nav == Decimal(".95")
    assert bars[1].total_return == Decimal("1.01")
    assert provider.get_fund_profile("012885").name == "测试A"
    assert len(calls) == 1


def test_parser_never_executes_js():
    with pytest.raises(ProviderError):
        extract_json("var field = evil();", "field")


def test_freshness_domestic_vs_qdii_weekend():
    monday = datetime(2026, 9, 14, 12, tzinfo=UTC)  # Monday 20:00 China
    assert is_fresh(date(2026, 9, 11), monday)
    assert not is_fresh(date(2026, 9, 10), monday)
    assert is_fresh(date(2026, 9, 10), monday, qdii=True)
    assert not is_fresh(date(2026, 9, 16), monday)


def test_http_failure_and_symbol_mismatch():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403)))
    with pytest.raises(ProviderError):
        EastmoneyProvider(client=client).get_fund_profile("012885")
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=SCRIPT)))
    with pytest.raises(ProviderError):
        EastmoneyProvider(client=client).get_fund_profile("000001")
