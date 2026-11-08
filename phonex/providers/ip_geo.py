from __future__ import annotations

from ..models import ProviderResult
from .base import Provider, ProviderContext


class IpGeoProvider(Provider):
    name = "ip_geo"
    description = "تحديد موقع IP عبر ip-api (يُستخدم في سيرفر الالتقاط)"

    async def run(self, ctx: ProviderContext) -> ProviderResult:
        res = self.result()
        res.skipped = True
        res.error = "يُشغَّل عبر السيرفر على IP الزائر"
        return res


async def lookup_ip(http, ip: str) -> dict:
    """Resolve coarse geolocation for an IP address."""
    if not ip or ip.startswith(("127.", "10.", "192.168.", "172.16.")):
        return {}
    data = await http.get_json(
        f"http://ip-api.com/json/{ip}",
        params={"fields": "status,country,regionName,city,isp,org,as,lat,lon,timezone,query"},
    )
    if isinstance(data, dict) and data.get("status") == "success":
        return data
    return {}