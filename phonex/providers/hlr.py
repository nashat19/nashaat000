from __future__ import annotations

from ..models import ProviderResult
from .base import Provider, ProviderContext


class HlrProvider(Provider):
    name = "hlr"
    description = "استعلام HLR مباشر عبر Numverify (يتطلب مفتاحاً)"
    requires_key = "NUMVERIFY_KEY"

    async def run(self, ctx: ProviderContext) -> ProviderResult:
        res = self.result()
        key = ctx.key("NUMVERIFY_KEY")
        if not key:
            return self.skip("NUMVERIFY_KEY غير مضبوط")

        data = await ctx.http.get_json(
            "http://apilayer.net/api/validate",
            params={"access_key": key, "number": ctx.phone.e164, "format": "1"},
        )
        if not isinstance(data, dict):
            res.ok = False
            res.error = "استجابة غير صالحة من المزوّد"
            return res
        if data.get("success") is False:
            res.ok = False
            res.error = str(data.get("error", {}).get("info", "خطأ مزوّد"))
            return res

        res.raw = data
        mapping = {
            "valid": ("valid", "high"),
            "number": ("e164", "high"),
            "local_format": ("national", "high"),
            "country_code": ("country_code", "high"),
            "country_name": ("country_name", "high"),
            "location": ("location", "medium"),
            "carrier": ("carrier", "high"),
            "line_type": ("line_type", "high"),
        }
        for src, (dst, conf) in mapping.items():
            value = data.get(src)
            if value not in (None, "", False):
                res.add(dst, value, confidence=conf)
        return res