from __future__ import annotations

import base64

from ..models import ProviderResult
from .base import Provider, ProviderContext


class BreachProvider(Provider):
    name = "breach"
    description = "فحص التسريبات عبر HIBP و LeakCheck و DeHashed"

    async def run(self, ctx: ProviderContext) -> ProviderResult:
        res = self.result()
        digits = ctx.phone.digits
        if not digits:
            res.ok = False
            res.error = "لا توجد أرقام"
            return res

        checked = False

        hibp_key = ctx.key("HIBP_KEY")
        if hibp_key:
            checked = True
            data = await ctx.http.get_json(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{digits}",
                params={"truncateResponse": "false"},
                headers={"hibp-api-key": hibp_key, "User-Agent": "PhoneX"},
            )
            if isinstance(data, list):
                for breach in data:
                    res.add(
                        "breach",
                        breach.get("Name", "?"),
                        confidence="high",
                        note=breach.get("Title", ""),
                    )
            elif data is None:
                res.add("hibp", "لا نتائج أو خطأ", confidence="low")

        leakcheck_key = ctx.key("LEAKCHECK_KEY")
        if leakcheck_key:
            checked = True
            data = await ctx.http.get_json(
                "https://leakcheck.io/api/public",
                params={"key": leakcheck_key, "check": digits},
            )
            if isinstance(data, dict) and data.get("success"):
                for item in data.get("result", []) or []:
                    res.add(
                        "leak",
                        item.get("source", "?"),
                        confidence="high",
                        note=str(item.get("fields", "")),
                    )

        email = ctx.key("DEHASHED_EMAIL")
        dkey = ctx.key("DEHASHED_KEY")
        if email and dkey:
            checked = True
            auth = base64.b64encode(f"{email}:{dkey}".encode()).decode()
            data = await ctx.http.get_json(
                "https://api.dehashed.com/search",
                params={"query": f'phone:"{digits}"', "size": "20"},
                headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
            )
            if isinstance(data, dict):
                for entry in data.get("entries", []) or []:
                    res.add(
                        "dehashed",
                        entry.get("email") or entry.get("username") or "?",
                        confidence="medium",
                        note=str(entry.get("database_name", "")),
                    )

        if not checked:
            return self.skip("لا مفاتيح تسريبات مضبوطة")
        return res