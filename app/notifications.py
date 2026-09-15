import httpx

from app.providers.base import ProviderError
from app.providers.http import request


def notify_telegram(settings, day, recommendations, client=None):
    if not settings.telegram_enabled:
        return "DISABLED"
    if not settings.telegram_bot_token.get_secret_value() or not settings.telegram_chat_id:
        raise ProviderError("Telegram credentials missing")
    message = f"基金研究日报 {day}\n"
    for r in recommendations:
        message += f"{r['symbol']} {r['action']} CNY {r['proposed_amount']}\n"
    message += "详情请查看本地仪表盘。未执行任何交易。"
    own = client is None
    client = client or httpx.Client()
    try:
        response = request(
            client,
            "POST",
            "https://api.telegram.org/bot"
            + settings.telegram_bot_token.get_secret_value()
            + "/sendMessage",
            provider="telegram",
            operation="send",
            json={"chat_id": settings.telegram_chat_id, "text": message[:4000]},
        )
        if not response.json().get("ok"):
            raise ProviderError("Telegram rejected notification")
        return "OK"
    finally:
        if own:
            client.close()
