from datetime import UTC, datetime

import httpx

from app.config import Settings
from app.macro import fetch_fred
from app.notifications import notify_telegram


def test_fred_mock_preserves_sources_and_skips_missing_values():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "observations": [
                        {"date": "2026-09-14", "value": "1.5"},
                        {"date": "2026-09-13", "value": "."},
                    ]
                },
            )
        )
    )
    values, errors = fetch_fred(
        Settings(fred_api_key="fake"), datetime(2026, 9, 15, tzinfo=UTC), client
    )
    assert not errors and len(values) == 4
    assert all(v["source"].startswith("https://fred.stlouisfed.org/series/") for v in values)


def test_telegram_is_opt_in_and_mock_only():
    assert notify_telegram(Settings(telegram_enabled=False), "today", []) == "DISABLED"
    captured = []

    def handler(request):
        captured.append(request.content)
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    status = notify_telegram(
        Settings(telegram_enabled=True, telegram_bot_token="fake", telegram_chat_id="fake"),
        "2026-09-15",
        [],
        client,
    )
    assert status == "OK" and len(captured) == 1
