"""Spam / scam reputation via search-engine dorks."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from ..models import Finding
from .base import Context, Provider

DDG_LITE = "https://lite.duckduckgo.com/lite/?q={query}"
LINK_RE = re.compile(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

KEYWORDS = {
    "spam": ["spam", "scam", "احتيال", "نصب", "مزعج"],
    "telemarketing": ["telemarketing", "تسويق", "اعلان", "إعلان"],
    "fraud": ["fraud", "fake", "وهمي", "مزيف"],
}

class ReputationProvider(Provider):
    name = "reputation"
    category = "reputation"

    async def run(self, ctx: Context) -> list[Finding]:
        number = ctx.target.e164 or ctx.target.raw
        query = f'"{number}" (spam OR scam OR fraud OR نصب OR احتيال)'
        url = DDG_LITE.format(query=quote_plus(query))
        try:
            html = await ctx.http.get_text(url)
        except Exception:
            return []
        out: list[Finding] = []
        hits = LINK_RE.findall(html)
        for href, title in hits[:10]:
            clean = TAG_RE.sub("", title).strip()
            if not clean:
                continue
            lowered = clean.lower()
            for label, words in KEYWORDS.items():
                if any(word in lowered for word in words):
                    out.append(self.finding(f"report_{label}", f"{clean} -> {href}", 0.6, href))
                    break
        if not out:
            out.append(self.finding("reputation", "no_public_reports", 0.4, url))
        return out