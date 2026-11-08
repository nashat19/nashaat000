from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlsplit

import httpx

from .ratelimit import TokenBucket
from .utils import DEFAULT_UA

log = logging.getLogger("phonex.http")


class HttpClient:
    """Resilient async HTTP client with retries and per-host throttling."""

    def __init__(
        self,
        timeout: float = 12.0,
        retries: int = 2,
        backoff: float = 0.8,
        proxy: str | None = None,
        user_agent: str = DEFAULT_UA,
        verify: bool = True,
    ) -> None:
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = backoff
        self.proxy = proxy
        self.user_agent = user_agent
        self.verify = verify
        self.bucket = TokenBucket()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HttpClient":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            verify=self.verify,
            proxy=self.proxy,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            },
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(self, method: str, url: str, **kw: Any) -> httpx.Response | None:
        if self._client is None:
            raise RuntimeError("HttpClient must be used as an async context manager")
        host = urlsplit(url).netloc
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            await self.bucket.acquire(host)
            try:
                response = await self._client.request(method, url, **kw)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    await asyncio.sleep(self.backoff * (2**attempt))
                    continue
                return response
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff * (2**attempt))
                    continue
        log.debug("request failed %s %s: %s", method, url, last_error)
        return None

    async def get(self, url: str, **kw: Any) -> httpx.Response | None:
        return await self.request("GET", url, **kw)

    async def get_json(self, url: str, **kw: Any) -> Any:
        response = await self.get(url, **kw)
        if response is None or response.status_code >= 400:
            return None
        try:
            return response.json()
        except ValueError:
            return None