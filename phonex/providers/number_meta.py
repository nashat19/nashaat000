from __future__ import annotations

from ..models import ProviderResult
from .base import Provider, ProviderContext


class NumberMetaProvider(Provider):
    name = "number_meta"
    description = "بيانات وصفية محلية للرقم: الدولة، النوع، المنطقة الزمنية"

    async def run(self, ctx: ProviderContext) -> ProviderResult:
        res = self.result()
        phone = ctx.phone
        if not phone.e164:
            res.ok = False
            res.error = "رقم غير قابل للتطبيع"
            return res

        res.add("e164", phone.e164, confidence="high")
        if phone.region:
            res.add("region", phone.region, confidence="high")
        if phone.country_code:
            res.add("country_code", "+" + phone.country_code, confidence="high")
        res.add("line_type", phone.line_type, confidence="medium")
        if phone.carrier:
            res.add("carrier_lib", phone.carrier, confidence="medium")
        for tz in phone.timezones:
            res.add("timezone", tz, confidence="medium")
        res.add("valid", phone.valid, confidence="high")
        res.add("possible", phone.possible, confidence="high")
        if phone.national:
            res.add("national_format", phone.national, confidence="high")
        res.raw = phone.to_dict()
        return res