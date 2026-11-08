from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Config
from ..http import HttpClient
from ..models import ProviderResult
from ..phone import PhoneInfo


@dataclass
class ProviderContext:
    phone: PhoneInfo
    config: Config
    http: HttpClient

    def key(self, name: str) -> str:
        return self.config.key(name)


class Provider:
    name = "base"
    requires_key: str | None = None
    description = ""

    def enabled(self, ctx: ProviderContext) -> bool:
        if self.requires_key and not ctx.key(self.requires_key):
            return False
        return True

    async def run(self, ctx: ProviderContext) -> ProviderResult:  # pragma: no cover
        raise NotImplementedError

    def skip(self, reason: str) -> ProviderResult:
        return ProviderResult(provider=self.name, ok=True, skipped=True, error=reason)

    def result(self) -> ProviderResult:
        return ProviderResult(provider=self.name)

    def meta(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "requires_key": self.requires_key,
        }