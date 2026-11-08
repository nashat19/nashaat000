from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .utils import DEFAULT_UA, parse_bool, parse_float, parse_int

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.example.yaml"


@dataclass
class HttpConfig:
    timeout: float = 12.0
    retries: int = 2
    backoff: float = 0.8
    proxy: str | None = None
    user_agent: str = DEFAULT_UA
    verify_tls: bool = True


@dataclass
class CaptureConfig:
    host: str = "0.0.0.0"
    port: int = 8088
    public_base: str = "http://127.0.0.1:8088"
    db_path: str = "data/phonex.db"
    dashboard_token: str = "change-me-please"
    session_ttl: int = 86400
    geolocation: bool = True
    pretext_title: str = "بوابة التحقق الموحّدة"
    pretext_subtitle: str = "جارٍ التحقق من هوية الرابط وصلاحية الجلسة"
    brand: str = "SecureGate"


@dataclass
class ProvidersConfig:
    enabled: list[str] = field(
        default_factory=lambda: [
            "number_meta",
            "mccmnc",
            "messaging",
            "social_dorks",
            "hlr",
            "breach",
        ]
    )
    timeout: float = 20.0
    concurrency: int = 6


@dataclass
class OutputConfig:
    dir: str = "out"
    formats: list[str] = field(default_factory=lambda: ["json", "md", "html"])


@dataclass
class Config:
    http: HttpConfig = field(default_factory=HttpConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    providers: ProvidersConfig = field(default_factory=ProvidersConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    default_region: str = "IQ"
    keys: dict[str, str] = field(default_factory=dict)

    def key(self, name: str) -> str:
        return (self.keys.get(name) or os.environ.get(name) or "").strip()


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    return value if isinstance(value, dict) else {}


def load(path: str | Path | None = None) -> Config:
    """Load configuration from YAML plus environment overrides."""
    cfg = Config()
    target = Path(path) if path else DEFAULT_CONFIG_PATH
    if target.exists():
        try:
            data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            data = {}
        if isinstance(data, dict):
            http = _section(data, "http")
            cfg.http.timeout = parse_float(http.get("timeout"), cfg.http.timeout)
            cfg.http.retries = parse_int(http.get("retries"), cfg.http.retries)
            cfg.http.backoff = parse_float(http.get("backoff"), cfg.http.backoff)
            cfg.http.proxy = http.get("proxy") or None
            cfg.http.verify_tls = parse_bool(http.get("verify_tls"), True)

            cap = _section(data, "capture")
            cfg.capture.host = str(cap.get("host", cfg.capture.host))
            cfg.capture.port = parse_int(cap.get("port"), cfg.capture.port)
            cfg.capture.public_base = str(cap.get("public_base", cfg.capture.public_base))
            cfg.capture.db_path = str(cap.get("db_path", cfg.capture.db_path))
            cfg.capture.dashboard_token = str(
                cap.get("dashboard_token", cfg.capture.dashboard_token)
            )
            cfg.capture.session_ttl = parse_int(cap.get("session_ttl"), cfg.capture.session_ttl)
            cfg.capture.geolocation = parse_bool(cap.get("geolocation"), True)
            cfg.capture.pretext_title = str(cap.get("pretext_title", cfg.capture.pretext_title))
            cfg.capture.pretext_subtitle = str(
                cap.get("pretext_subtitle", cfg.capture.pretext_subtitle)
            )
            cfg.capture.brand = str(cap.get("brand", cfg.capture.brand))

            prov = _section(data, "providers")
            enabled = prov.get("enabled")
            if isinstance(enabled, list) and enabled:
                cfg.providers.enabled = [str(x) for x in enabled]
            cfg.providers.timeout = parse_float(prov.get("timeout"), cfg.providers.timeout)
            cfg.providers.concurrency = parse_int(
                prov.get("concurrency"), cfg.providers.concurrency
            )

            out = _section(data, "output")
            cfg.output.dir = str(out.get("dir", cfg.output.dir))
            formats = out.get("formats")
            if isinstance(formats, list) and formats:
                cfg.output.formats = [str(x) for x in formats]

            cfg.default_region = str(data.get("default_region", cfg.default_region))

    env = os.environ
    cfg.capture.host = env.get("PHONEX_HOST", cfg.capture.host)
    cfg.capture.port = parse_int(env.get("PHONEX_PORT"), cfg.capture.port)
    cfg.capture.public_base = env.get("PHONEX_PUBLIC_BASE", cfg.capture.public_base)
    cfg.capture.db_path = env.get("PHONEX_DB_PATH", cfg.capture.db_path)
    cfg.capture.dashboard_token = env.get(
        "PHONEX_DASHBOARD_TOKEN", cfg.capture.dashboard_token
    )
    cfg.http.timeout = parse_float(env.get("PHONEX_HTTP_TIMEOUT"), cfg.http.timeout)
    cfg.http.retries = parse_int(env.get("PHONEX_HTTP_RETRIES"), cfg.http.retries)
    cfg.http.proxy = env.get("PHONEX_PROXY") or cfg.http.proxy
    cfg.default_region = env.get("PHONEX_REGION", cfg.default_region)

    for name in (
        "NUMVERIFY_KEY",
        "HIBP_KEY",
        "LEAKCHECK_KEY",
        "DEHASHED_EMAIL",
        "DEHASHED_KEY",
        "IPINFO_TOKEN",
    ):
        value = env.get(name)
        if value:
            cfg.keys[name] = value

    return cfg