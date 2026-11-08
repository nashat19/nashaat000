from __future__ import annotations

import hashlib
import json
import re
import secrets
import string
import time
from datetime import datetime, timezone
from typing import Any

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_ALPHABET = string.ascii_lowercase + string.digits
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def utcnow() -> str:
    """ISO-8601 UTC timestamp with second precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def epoch() -> int:
    return int(time.time())


def token(n: int = 14) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mask_number(e164: str) -> str:
    digits = re.sub(r"\D", "", e164 or "")
    if len(digits) < 7:
        return e164 or ""
    return "+" + digits[:3] + "*" * (len(digits) - 6) + digits[-3:]


def jdump(obj: Any, indent: int | None = None) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=indent, default=str)


def jload(raw: str | bytes | None, default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def slugify(value: str, fallback: str = "item") -> str:
    slug = _SLUG_RE.sub("-", (value or "").lower()).strip("-")
    return slug or fallback


def human_bytes(n: int | float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def truncate(value: str, limit: int = 120) -> str:
    value = (value or "").replace("\n", " ").strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def dedupe(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for item in items:
        key = jdump(item, indent=None) if not isinstance(item, str) else item
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def parse_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_float(value: Any, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default