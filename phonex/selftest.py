from __future__ import annotations

import sys

from . import analyze

IPHONE = {
    "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
    "max_touch_points": 5,
    "platform": "iPhone",
    "languages": ["ar-IQ"],
    "tz_offset": "+03:00",
    "tz_country": "IQ",
    "webgl_renderer": "Apple GPU",
    "canvas_hash": "a",
    "audio_hash": "b",
    "fonts": ["Arial"],
    "media_devices": "cam:2 mic:1 out:1",
}

WINDOWS = {
    "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "max_touch_points": 0,
    "platform": "Win32",
    "languages": ["en-US"],
    "tz_offset": "-05:00",
    "tz_country": "US",
    "webgl_renderer": "ANGLE (NVIDIA GeForce RTX 3060)",
    "canvas_hash": "c",
    "audio_hash": "d",
    "fonts": ["Calibri"],
    "media_devices": "cam:1 mic:1 out:2",
}

ANDROID = {
    "ua": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36",
    "max_touch_points": 5,
    "platform": "Linux armv8l",
    "languages": ["en-GB"],
    "tz_offset": "+01:00",
    "tz_country": "GB",
    "webgl_renderer": "Adreno (TM) 740",
    "canvas_hash": "e",
    "audio_hash": "f",
    "fonts": [],
    "media_devices": "",
    "webdriver": True,
}

def check(label: str, got, want) -> bool:
    ok = got == want
    print(f"{'✓' if ok else '✗'} {label}: {got!r}" + ("" if ok else f" (متوقع {want!r})"))
    return ok

def main() -> int:
    failures = 0

    failures += not check("iphone class", analyze.device_class(IPHONE), "phone")
    failures += not check("iphone os", analyze.os_family(IPHONE), "iOS 17.4")
    failures += not check("iphone browser", analyze.browser(IPHONE), "Safari 17.4")
    failures += not check("iphone gpu", analyze.gpu_vendor(IPHONE), "Apple")

    failures += not check("win class", analyze.device_class(WINDOWS), "desktop")
    failures += not check("win os", analyze.os_family(WINDOWS), "Windows 10/11")
    failures += not check("win browser", analyze.browser(WINDOWS), "Chrome 124.0.0.0")
    failures += not check("win gpu", analyze.gpu_vendor(WINDOWS), "NVIDIA")

    failures += not check("android os", analyze.os_family(ANDROID), "Android 14")
    failures += not check("android gpu", analyze.gpu_vendor(ANDROID), "Qualcomm Adreno")

    failures += not check("tz +03:00", analyze.tz_offset_minutes("+03:00"), 180)
    failures += not check("tz -05:30", analyze.tz_offset_minutes("-05:30"), -330)
    failures += not check("tz bad", analyze.tz_offset_minutes("bad"), None)

    failures += not check("prec 10", analyze.geo_precision(10), "دقيقة جداً")
    failures += not check("prec 900", analyze.geo_precision(900), "خشنة")
    failures += not check("prec none", analyze.geo_precision(None), "مجهولة")

    flags = analyze.mismatch_flags(WINDOWS, {"countryCode": "DE"})
    failures += not check("flag tz/ip", any("تعارض منطقة زمنية" in f for f in flags), True)
    failures += not check("flag platform", any("platform" in f for f in flags), True)

    android_flags = analyze.mismatch_flags(ANDROID, {})
    failures += not check("flag webdriver", any("webdriver" in f for f in android_flags), True)

    high = analyze.dossier(IPHONE, {"countryCode": "IQ"}, [{"acc": 15}])
    low = analyze.dossier({}, {}, [])
    failures += not check("high verdict", high["verdict"], "عالية")
    failures += not check("low verdict", low["verdict"], "معدومة")
    failures += not check("high precision", high["geo_precision"], "دقيقة جداً")

    merged = analyze.merge(high, low)
    failures += not check("merge keeps confidence", merged["confidence"], high["confidence"])
    failures += not check("merge keeps os", merged["os"], high["os"])

    events = [{"kind": "open"}, {"kind": "fingerprint"}, {"kind": "location"}]
    failures += not check("stage", analyze.stage_of(events), "location")
    failures += not check("stage empty", analyze.stage_of([]), "none")

    print()
    if failures:
        print(f"فشل {failures} اختبار")
        return 1
    print("كل الاختبارات نجحت")
    return 0

if __name__ == "__main__":
    sys.exit(main())