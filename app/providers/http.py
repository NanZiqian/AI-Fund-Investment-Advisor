import logging
import time

import httpx

from app.providers.base import ProviderError

logger = logging.getLogger(__name__)


def request(client, method, url, *, provider, operation, symbol="", **kwargs):
    for attempt in range(3):
        try:
            response = client.request(method, url, timeout=25, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, OSError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "provider=%s operation=%s symbol=%s retry=%s error=%s status=%s",
                provider,
                operation,
                symbol,
                attempt,
                type(exc).__name__,
                status,
            )
            if attempt == 2 or status in (400, 401, 403, 404):
                raise ProviderError(f"{provider}/{operation}: {type(exc).__name__}") from None
            time.sleep(0.2 * 2**attempt)
    raise ProviderError("Request failed")
