from __future__ import annotations

from ..models import ProviderResult
from .base import Provider, ProviderContext

# بادئات MCC-MNC شائعة (دولة → بادئة وطنية → مشغّل)
PREFIX_TABLE: dict[str, dict[str, tuple[str, str]]] = {
    "IQ": {
        "770": ("41820", "Asiacell"),
        "771": ("41820", "Asiacell"),
        "780": ("41805", "Korek Telecom"),
        "781": ("41805", "Korek Telecom"),
        "790": ("41840", "Korek Telecom"),
        "791": ("41840", "Korek Telecom"),
        "750": ("41830", "Zain Iraq"),
        "751": ("41830", "Zain Iraq"),
        "760": ("41830", "Zain Iraq"),
        "761": ("41830", "Zain Iraq"),
    },
    "SA": {
        "50": ("42001", "STC"),
        "53": ("42001", "STC"),
        "55": ("42004", "Mobily"),
        "56": ("42004", "Mobily"),
        "59": ("42003", "Zain KSA"),
    },
    "AE": {
        "50": ("42402", "Etisalat"),
        "52": ("42402", "Etisalat"),
        "55": ("42403", "du"),
        "56": ("42403", "du"),
    },
    "EG": {
        "10": ("60203", "Etisalat Misr"),
        "11": ("60202", "Vodafone Egypt"),
        "12": ("60201", "Orange Egypt"),
        "15": ("60204", "WE"),
    },
    "TR": {
        "532": ("28601", "Turkcell"),
        "542": ("28602", "Vodafone TR"),
        "505": ("28603", "Turk Telekom"),
    },
    "GB": {
        "74": ("23410", "O2 UK"),
        "77": ("23415", "Vodafone UK"),
        "78": ("23430", "EE"),
    },
    "US": {
        "20": ("310260", "T-Mobile US"),
        "30": ("310410", "AT&T"),
        "40": ("311480", "Verizon"),
    },
}


class MccMncProvider(Provider):
    name = "mccmnc"
    description = "تحديد المشغّل عبر جدول MCC-MNC المحلي"

    async def run(self, ctx: ProviderContext) -> ProviderResult:
        res = self.result()
        phone = ctx.phone
        region = phone.region
        if not region or region not in PREFIX_TABLE:
            res.skipped = True
            res.error = f"لا يوجد جدول بادئات للمنطقة {region or '؟'}"
            return res

        national = phone.digits
        if phone.country_code and national.startswith(phone.country_code):
            national = national[len(phone.country_code) :]

        table = PREFIX_TABLE[region]
        for length in (3, 2):
            prefix = national[:length]
            hit = table.get(prefix)
            if hit:
                mccmnc, operator = hit
                res.add("mcc_mnc", mccmnc, confidence="high")
                res.add("operator", operator, confidence="high")
                res.add("prefix", prefix, confidence="high")
                res.raw = {"region": region, "prefix": prefix, "mcc_mnc": mccmnc}
                return res

        res.skipped = True
        res.error = "البادئة غير موجودة في الجدول المحلي"
        return res