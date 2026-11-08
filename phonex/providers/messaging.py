from __future__ import annotations

import re

from ..models import ProviderResult
from .base import Provider, ProviderContext

WA_INVALID = re.compile(r"phone number shared via url is invalid", re.I)
TG_NO_USER = re.compile(r"tgme_page_extra|tgme_page_title", re.I)


class MessagingProvider(Provider):
    name = "messaging"
    description = "فحص وجود الرقم على واتساب وتلغرام"

    async def run(self, ctx: ProviderContext) -> ProviderResult:
        res = self.result()
        digits = ctx.phone.digits
        if not digits:
            res.ok = False
            res.error = "لا توجد أرقام"
            return res

        wa = await ctx.http.get(f"https://wa.me/{digits}")
        if wa is not None:
            body = wa.text or ""
            if wa.status_code == 200 and WA_INVALID.search(body):
                res.add("whatsapp", False, confidence="high", url=f"https://wa.me/{digits}")
            elif wa.status_code == 200:
                res.add("whatsapp", True, confidence="medium", url=f"https://wa.me/{digits}")
            else:
                res.add("whatsapp", "unknown", confidence="low")

        tg = await ctx.http.get(
            f"https://t.me/+{digits}", follow_redirects=False
        )
        if tg is not None:
            location = tg.headers.get("location", "")
            if tg.status_code in (301, 302, 303, 307, 308) and location:
                username = location.rstrip("/").rsplit("/", 1)[-1]
                if username and not username.startswith("+"):
                    res.add("telegram", True, confidence="high", url=f"https://t.me/{username}")
                    res.add("telegram_username", username, confidence="high")
                else:
                    res.add("telegram", False, confidence="medium")
            elif tg.status_code == 200:
                res.add("telegram", bool(TG_NO_USER.search(tg.text or "")), confidence="low")
        return res