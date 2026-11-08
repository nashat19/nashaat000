"""استنباط استخباراتي من بصمة الجهاز + الموقع + IP.

كل الدوال نقية (بدون I/O) لتعمل داخل السيرفر وفي الـ CLI وفي الاختبارات.
"""
from __future__ import annotations

import re
from typing import Any

_ANDROID = re.compile(r"android\s+([\d.]+)", re.I)
_IOS = re.compile(r"(?:iphone|ipad|ipod).*?os\s+([\d_]+)", re.I)
_WIN = re.compile(r"windows nt\s+([\d.]+)", re.I)
_MAC = re.compile(r"mac os x\s+([\d_]+)", re.I)
_CHROME = re.compile(r"(?:chrome|crios)/([\d.]+)", re.I)
_FIREFOX = re.compile(r"firefox/([\d.]+)", re.I)
_SAFARI = re.compile(r"version/([\d.]+).*safari", re.I)
_EDGE = re.compile(r"edg(?:e|ios|a)?/([\d.]+)", re.I)
_SAMSUNG = re.compile(r"samsungbrowser/([\d.]+)", re.I)
_OPERA = re.compile(r"(?:opr|opera)/([\d.]+)", re.I)
_TZ_OFFSET = re.compile(r"^([+-])(\d{2}):(\d{2})$")

_WIN_NAMES = {"10.0": "10/11", "6.3": "8.1", "6.2": "8", "6.1": "7"}

_GPU_VENDORS = (
    ("apple", "Apple"),
    ("adreno", "Qualcomm Adreno"),
    ("mali", "ARM Mali"),
    ("powervr", "PowerVR"),
    ("intel", "Intel"),
    ("nvidia", "NVIDIA"),
    ("radeon", "AMD"),
    ("amd", "AMD"),
    ("swiftshader", "SwiftShader"),
    ("llvmpipe", "llvmpipe"),
)

_MENA = {"IQ", "SA", "AE", "EG", "KW", "QA", "BH", "OM", "JO", "LB", "SY", "YE", "PS"}

STAGES = ("open", "fingerprint", "location", "ip_geo")

def _ua(fp: dict[str, Any]) -> str:
    return str(fp.get("ua") or "")

def _touch(fp: dict[str, Any]) -> int:
    try:
        return int(fp.get("max_touch_points") or 0)
    except (TypeError, ValueError):
        return 0

def device_class(fp: dict[str, Any]) -> str:
    ua = _ua(fp).lower()
    touch = _touch(fp)
    if "ipad" in ua or ("macintosh" in ua and touch > 1):
        return "tablet"
    if "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if "mobile" in ua or touch > 0:
        return "phone"
    if any(x in ua for x in ("windows", "macintosh", "x11", "linux", "cros")):
        return "desktop"
    return "unknown"

def os_family(fp: dict[str, Any]) -> str:
    ua = _ua(fp)
    m = _IOS.search(ua)
    if m:
        return "iOS " + m.group(1).replace("_", ".")
    m = _ANDROID.search(ua)
    if m:
        return "Android " + m.group(1)
    m = _WIN.search(ua)
    if m:
        return "Windows " + _WIN_NAMES.get(m.group(1), m.group(1))
    m = _MAC.search(ua)
    if m:
        return "macOS " + m.group(1).replace("_", ".")
    low = ua.lower()
    if "cros" in low:
        return "ChromeOS"
    if "x11" in low or "linux" in low:
        return "Linux"
    return "unknown"

def browser(fp: dict[str, Any]) -> str:
    ua = _ua(fp)
    for rx, name in (
        (_EDGE, "Edge"),
        (_SAMSUNG, "Samsung Internet"),
        (_OPERA, "Opera"),
        (_FIREFOX, "Firefox"),
        (_CHROME, "Chrome"),
        (_SAFARI, "Safari"),
    ):
        m = rx.search(ua)
        if m:
            return f"{name} {m.group(1)}"
    return "unknown"

def gpu_vendor(fp: dict[str, Any]) -> str:
    renderer = str(fp.get("webgl_renderer") or "").lower()
    for key, name in _GPU_VENDORS:
        if key in renderer:
            return name
    return "unknown"

def network_class(fp: dict[str, Any]) -> str:
    conn = fp.get("connection") or {}
    if not isinstance(conn, dict):
        return "unknown"
    effective = str(conn.get("effectiveType") or "")
    downlink = conn.get("downlink")
    if effective in ("slow-2g", "2g"):
        return "ضعيفة " + effective
    if effective == "3g":
        return "متوسطة 3g"
    if effective == "4g":
        return "جيدة 4g"
    if downlink is not None:
        return f"غير معروفة ({downlink}Mbps)"
    return "unknown"

def tz_offset_minutes(offset: Any) -> int | None:
    m = _TZ_OFFSET.match(str(offset or ""))
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    return sign * (int(m.group(2)) * 60 + int(m.group(3)))

def geo_precision(acc: Any) -> str:
    try:
        value = float(acc)
    except (TypeError, ValueError):
        return "مجهولة"
    if value <= 20:
        return "دقيقة جداً"
    if value <= 60:
        return "دقيقة"
    if value <= 200:
        return "مقبولة"
    if value <= 1500:
        return "خشنة"
    return "شبه معدومة"

def mismatch_flags(fp: dict[str, Any], ip_geo: dict[str, Any] | None) -> list[str]:
    flags: list[str] = []
    ip_country = str((ip_geo or {}).get("countryCode") or "").upper()
    tz_country = str(fp.get("tz_country") or "").upper()
    if ip_country and tz_country and ip_country != tz_country:
        flags.append(f"تعارض منطقة زمنية ({tz_country}) مع IP ({ip_country})")

    langs = fp.get("languages") or []
    if isinstance(langs, list) and langs and ip_country:
        primary = str(langs[0]).split("-")[0].lower()
        if primary and primary not in ("en", "ar") and ip_country in _MENA:
            flags.append(f"لغة الجهاز ({primary}) لا تطابق بلد IP ({ip_country})")

    platform = str(fp.get("platform") or "").lower()
    ua = _ua(fp).lower()
    if platform and ua and platform.split()[0] not in ua and "linux" not in platform:
        flags.append("platform لا يطابق UA")

    if fp.get("webdriver"):
        flags.append("متصفح مؤتمت (webdriver)")

    if fp.get("timezone") and fp.get("tz_offset"):
        flags.append("إزاحة زمنية مُصرّحة يدوياً")

    if not fp.get("webgl_renderer"):
        flags.append("لا يوجد WebGL (متصفح مقيّد أو وكيل)")

    return flags

def confidence(fp: dict[str, Any], ip_geo: dict[str, Any] | None, locs: list[dict[str, Any]]) -> int:
    score = 0
    if fp.get("ua"):
        score += 2
    if fp.get("webgl_renderer"):
        score += 2
    if fp.get("canvas_hash"):
        score += 2
    if fp.get("audio_hash"):
        score += 1
    if fp.get("fonts"):
        score += 1
    if fp.get("media_devices"):
        score += 1
    if ip_geo:
        score += 2
    if locs:
        score += 3
    for loc in locs:
        try:
            if float(loc.get("acc") or 9999) <= 60:
                score += 3
                break
        except (TypeError, ValueError):
            continue
    return score

def verdict(score: int) -> str:
    if score >= 18:
        return "عالية"
    if score >= 11:
        return "متوسطة"
    if score >= 5:
        return "منخفضة"
    return "معدومة"

def dossier(
    fp: dict[str, Any],
    ip_geo: dict[str, Any] | None = None,
    locs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """بناء ملف استخباراتي كامل من بصمة وموقع وIP."""
    locs = locs or []
    score = confidence(fp, ip_geo, locs)
    last_acc = locs[-1].get("acc") if locs else None
    return {
        "device_class": device_class(fp),
        "os": os_family(fp),
        "browser": browser(fp),
        "gpu_vendor": gpu_vendor(fp),
        "network": network_class(fp),
        "tz_offset_min": tz_offset_minutes(fp.get("tz_offset")),
        "geo_precision": geo_precision(last_acc) if locs else "لا موقع",
        "mismatches": mismatch_flags(fp, ip_geo),
        "confidence": score,
        "verdict": verdict(score),
        "ip_country": str((ip_geo or {}).get("countryCode") or ""),
        "ip_city": str((ip_geo or {}).get("city") or ""),
        "ip_isp": str((ip_geo or {}).get("isp") or ""),
        "fp_count": 1 if fp else 0,
        "loc_count": len(locs),
    }

def merge(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """دمج ملفين تراكمياً: أعلى ثقة، اتحاد التعارضات، أفضل قيم معروفة."""
    out = dict(new)
    out["confidence"] = max(int(old.get("confidence") or 0), int(new.get("confidence") or 0))
    out["verdict"] = verdict(out["confidence"])
    flags = list(
        dict.fromkeys(list(old.get("mismatches") or []) + list(new.get("mismatches") or []))
    )
    out["mismatches"] = flags
    for key in ("os", "browser", "gpu_vendor", "device_class", "network", "ip_country", "ip_city", "ip_isp"):
        if (old.get(key) or "unknown") not in ("unknown", "") and (new.get(key) or "unknown") in ("unknown", ""):
            out[key] = old[key]
    if old.get("geo_precision") and new.get("geo_precision") in (None, "لا موقع", "مجهولة"):
        out["geo_precision"] = old["geo_precision"]
    out["fp_count"] = max(int(old.get("fp_count") or 0), int(new.get("fp_count") or 0))
    out["loc_count"] = max(int(old.get("loc_count") or 0), int(new.get("loc_count") or 0))
    out["first_seen"] = old.get("first_seen") or new.get("first_seen")
    return out

def stage_of(events: list[dict[str, Any]]) -> str:
    """أبعد مرحلة وصل إليها الهدف."""
    seen = {str(e.get("kind")) for e in events}
    reached = "none"
    for stage in STAGES:
        if stage in seen:
            reached = stage
    return reached

def summary_line(d: dict[str, Any]) -> str:
    parts = [
        d.get("device_class") or "?",
        d.get("os") or "?",
        d.get("browser") or "?",
        d.get("gpu_vendor") or "?",
        f"ثقة {d.get('confidence', 0)} ({d.get('verdict', '?')})",
    ]
    if d.get("ip_country"):
        parts.append(f"IP {d['ip_country']}")
    if d.get("geo_precision") and d["geo_precision"] != "لا موقع":
        parts.append(f"موقع {d['geo_precision']}")
    return " · ".join(parts)

def timeline(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """تسلسل زمني مضغوط لتفاعل الهدف."""
    out: list[dict[str, Any]] = []
    for event in events:
        kind = str(event.get("kind") or "")
        if kind not in STAGES and kind != "dossier":
            continue
        out.append({"ts": event.get("ts"), "kind": kind, "ip": event.get("ip", "")})
    return out