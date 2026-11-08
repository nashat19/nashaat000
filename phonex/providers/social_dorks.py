from __future__ import annotations

from urllib.parse import quote_plus

from ..models import ProviderResult
from .base import Provider, ProviderContext

ENGINES = {
    "google": "https://www.google.com/search?q=",
    "bing": "https://www.bing.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/?q=",
    "yandex": "https://yandex.com/search/?text=",
}

DORK_TEMPLATES = [
    '"{n}"',
    '"{n}" site:facebook.com',
    '"{n}" site:instagram.com',
    '"{n}" site:linkedin.com',
    '"{n}" site:twitter.com OR site:x.com',
    '"{n}" site:telegram.me OR site:t.me',
    '"{n}" filetype:pdf',
    '"{n}" (سعر OR للبيع OR مطلوب)',
    '"{n}" (اسم OR عنوان OR سكن)',
    '"{n}" site:truecaller.com',
]


class SocialDorksProvider(Provider):
    name = "social_dorks"
    description = "توليد دوركات جاهزة وروابط ملفات مباشرة"

    async def run(self, ctx: ProviderContext) -> ProviderResult:
        res = self.result()
        phone = ctx.phone
        if not phone.e164:
            res.ok = False
            res.error = "رقم غير صالح"
            return res

        national = phone.national or phone.e164
        variants = {phone.e164, phone.digits, national, national.replace(" ", "")}

        for variant in sorted(variants):
            for template in DORK_TEMPLATES:
                query = template.format(n=variant)
                for engine, base in ENGINES.items():
                    res.add(
                        f"dork:{engine}",
                        base + quote_plus(query),
                        confidence="low",
                        note=query,
                    )

        direct = {
            "wa.me": f"https://wa.me/{phone.digits}",
            "t.me": f"https://t.me/+{phone.digits}",
            "truecaller": f"https://www.truecaller.com/search/iq/{phone.digits}",
            "viber": f"https://chats.viber.com/{phone.digits}",
            "sync.me": f"https://sync.me/search/?number={phone.digits}",
        }
        for name, url in direct.items():
            res.add(f"profile:{name}", url, confidence="medium", url=url)

        res.raw = {"variants": sorted(variants), "count": len(res.findings)}
        return res