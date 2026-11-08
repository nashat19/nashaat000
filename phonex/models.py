from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .utils import utcnow


@dataclass
class Finding:
    key: str
    value: Any
    source: str
    confidence: str = "medium"
    url: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "url": self.url,
            "note": self.note,
        }


@dataclass
class ProviderResult:
    provider: str
    ok: bool = True
    skipped: bool = False
    error: str = ""
    elapsed_ms: int = 0
    findings: list[Finding] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def add(self, key: str, value: Any, **kw: Any) -> None:
        self.findings.append(Finding(key=key, value=value, source=self.provider, **kw))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "ok": self.ok,
            "skipped": self.skipped,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
            "findings": [f.to_dict() for f in self.findings],
            "raw": self.raw,
        }


@dataclass
class Report:
    target: str
    e164: str = ""
    started_at: str = field(default_factory=utcnow)
    finished_at: str = ""
    phone: dict[str, Any] = field(default_factory=dict)
    results: list[ProviderResult] = field(default_factory=list)

    @property
    def findings(self) -> list[Finding]:
        out: list[Finding] = []
        for result in self.results:
            out.extend(result.findings)
        return out

    def score(self) -> int:
        weights = {"high": 3, "medium": 2, "low": 1}
        return sum(weights.get(f.confidence, 1) for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "e164": self.e164,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "score": self.score(),
            "phone": self.phone,
            "results": [r.to_dict() for r in self.results],
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class Session:
    token: str
    number: str
    label: str = ""
    created_at: str = ""
    expires_at: int = 0
    hits: int = 0
    ip_first: str = ""
    ua_first: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "number": self.number,
            "label": self.label,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hits": self.hits,
            "ip_first": self.ip_first,
            "ua_first": self.ua_first,
        }