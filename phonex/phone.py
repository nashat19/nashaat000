from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:  # pragma: no cover - optional dependency
    import phonenumbers
    from phonenumbers import NumberParseException, PhoneNumberType

    HAVE_PHONENUMBERS = True
except Exception:  # pragma: no cover
    phonenumbers = None  # type: ignore[assignment]
    NumberParseException = Exception  # type: ignore[assignment,misc]
    PhoneNumberType = None  # type: ignore[assignment]
    HAVE_PHONENUMBERS = False

_DIAL_CODES: dict[str, str] = {
    "IQ": "964", "SA": "966", "AE": "971", "KW": "965", "QA": "974",
    "BH": "973", "OM": "968", "JO": "962", "LB": "961", "SY": "963",
    "EG": "20", "MA": "212", "DZ": "213", "TN": "216", "LY": "218",
    "SD": "249", "YE": "967", "PS": "970", "TR": "90", "IR": "98",
    "US": "1", "CA": "1", "GB": "44", "DE": "49", "FR": "33",
    "IT": "39", "ES": "34", "NL": "31", "BE": "32", "SE": "46",
    "NO": "47", "DK": "45", "FI": "358", "PL": "48", "RU": "7",
    "UA": "380", "IN": "91", "PK": "92", "BD": "880", "CN": "86",
    "JP": "81", "KR": "82", "ID": "62", "MY": "60", "SG": "65",
    "TH": "66", "VN": "84", "PH": "63", "AU": "61", "NZ": "64",
    "BR": "55", "MX": "52", "AR": "54", "ZA": "27", "NG": "234",
    "KE": "254", "ET": "251", "GH": "233", "IL": "972", "AZ": "994",
    "GE": "995", "AM": "374", "KZ": "7", "UZ": "998", "AF": "93",
}

_CODE_TO_REGION = {v: k for k, v in _DIAL_CODES.items()}

_LINE_TYPES = {
    0: "fixed_line", 1: "mobile", 2: "fixed_line_or_mobile", 3: "toll_free",
    4: "premium_rate", 5: "shared_cost", 6: "voip", 7: "personal_number",
    8: "pager", 9: "uan", 10: "voicemail", 27: "unknown",
}


@dataclass
class PhoneInfo:
    raw: str
    e164: str = ""
    national: str = ""
    international: str = ""
    digits: str = ""
    country_code: str = ""
    region: str = ""
    line_type: str = "unknown"
    valid: bool = False
    possible: bool = False
    carrier: str = ""
    timezones: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.e164) and self.valid

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "e164": self.e164,
            "national": self.national,
            "international": self.international,
            "digits": self.digits,
            "country_code": self.country_code,
            "region": self.region,
            "line_type": self.line_type,
            "valid": self.valid,
            "possible": self.possible,
            "carrier": self.carrier,
            "timezones": list(self.timezones),
            "notes": list(self.notes),
        }


def _clean(raw: str) -> str:
    value = (raw or "").strip()
    value = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    value = value.replace(".", "").replace("\u00a0", "")
    if value.startswith("00"):
        value = "+" + value[2:]
    return value


def _fallback(raw: str, default_region: str) -> PhoneInfo:
    info = PhoneInfo(raw=raw)
    value = _clean(raw)
    if value.startswith("+"):
        digits = re.sub(r"\D", "", value)
    else:
        digits = re.sub(r"\D", "", value)
        code = _DIAL_CODES.get((default_region or "").upper(), "")
        if code and not digits.startswith(code):
            digits = code + digits.lstrip("0")
    if not digits:
        info.notes.append("لا توجد أرقام قابلة للتحليل")
        return info
    info.digits = digits
    info.e164 = "+" + digits
    info.international = info.e164
    info.national = digits
    for code in sorted(_CODE_TO_REGION, key=len, reverse=True):
        if digits.startswith(code):
            info.country_code = code
            info.region = _CODE_TO_REGION[code]
            break
    info.possible = 7 <= len(digits) <= 15
    info.valid = info.possible
    info.line_type = "unknown"
    info.notes.append("تحليل احتياطي بدون مكتبة phonenumbers")
    return info


def parse(raw: str, default_region: str = "IQ") -> PhoneInfo:
    """Parse and normalise a phone number into E.164 with metadata."""
    raw = (raw or "").strip()
    if not raw:
        return PhoneInfo(raw=raw, notes=["رقم فارغ"])

    if not HAVE_PHONENUMBERS:
        return _fallback(raw, default_region)

    region = (default_region or "IQ").upper()
    try:
        parsed = phonenumbers.parse(_clean(raw), region)
    except NumberParseException as exc:
        info = _fallback(raw, region)
        info.notes.append(f"phonenumbers: {exc}")
        return info

    info = PhoneInfo(raw=raw)
    info.valid = phonenumbers.is_valid_number(parsed)
    info.possible = phonenumbers.is_possible_number(parsed)
    info.country_code = str(parsed.country_code)
    info.region = phonenumbers.region_code_for_number(parsed) or ""
    info.e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    info.national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    info.international = phonenumbers.format_number(
        parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
    )
    info.digits = info.e164.lstrip("+")
    info.line_type = _LINE_TYPES.get(int(phonenumbers.number_type(parsed)), "unknown")
    try:
        info.carrier = phonenumbers.carrier.name_for_number(parsed, "en") or ""
    except Exception:
        info.carrier = ""
    try:
        info.timezones = list(phonenumbers.timezone.time_zones_for_number(parsed))
    except Exception:
        info.timezones = []
    return info