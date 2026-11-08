from __future__ import annotations

import asyncio
import logging
import time
from typing import Iterable

from .config import Config
from .http import HttpClient
from .models import ProviderResult, Report
from .phone import PhoneInfo
from .providers.base import ProviderContext
from .providers.registry import build

log = logging.getLogger("phonex.engine")


async def run_scan(
    phone: PhoneInfo,
    config: Config,
    providers: Iterable[str] | None = None,
) -> Report:
    """Run all enabled providers concurrently and aggregate findings."""
    report = Report(target=phone.raw, e164=phone.e164, phone=phone.to_dict())
    if not phone.e164:
        report.finished_at = report.started_at
        return report

    names = list(providers) if providers else list(config.providers.enabled)
    instances = build(names)
    semaphore = asyncio.Semaphore(max(1, config.providers.concurrency))

    async with HttpClient(
        timeout=config.http.timeout,
        retries=config.http.retries,
        backoff=config.http.backoff,
        proxy=config.http.proxy,
        user_agent=config.http.user_agent,
        verify=config.http.verify_tls,
    ) as http:
        ctx = ProviderContext(phone=phone, config=config, http=http)

        async def execute(provider) -> ProviderResult:
            if not provider.enabled(ctx):
                return provider.skip(f"مفتاح {provider.requires_key} مفقود")
            async with semaphore:
                started = time.perf_counter()
                try:
                    result = await asyncio.wait_for(
                        provider.run(ctx), timeout=config.providers.timeout
                    )
                except asyncio.TimeoutError:
                    result = ProviderResult(
                        provider=provider.name, ok=False, error="انتهت المهلة"
                    )
                except Exception as exc:  # noqa: BLE001
                    log.debug("provider %s failed: %s", provider.name, exc)
                    result = ProviderResult(
                        provider=provider.name, ok=False, error=str(exc)
                    )
                result.elapsed_ms = int((time.perf_counter() - started) * 1000)
                return result

        results = await asyncio.gather(*(execute(p) for p in instances))

    report.results = list(results)
    from .utils import utcnow

    report.finished_at = utcnow()
    return report