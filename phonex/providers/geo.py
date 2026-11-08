"""Approximate geolocation from country, region and timezone metadata."""

from __future__ import annotations

from ..models import Finding
from .base import Context, Provider

COUNTRY_CENTROID: dict[str, tuple[float, float]] = {
    "IQ": (33.2232, 43.6793), "SA": (23.8859, 45.0792), "AE": (23.4241, 53.8478),
    "EG": (26.8206, 30.8025), "JO": (30.5852, 36.2384), "KW": (29.3117, 47.4818),
    "QA": (25.3548, 51.1839), "BH": (26.0667, 50.5577), "OM": (21.4735, 55.9754),
    "LB": (33.8547, 35.8623), "SY": (34.8021, 38.9968), "YE": (15.5527, 48.5164),
    "PS": (31.9522, 35.2332), "TR": (38.9637, 35.2433), "IR": (32.4279, 53.6880),
    "US": (37.0902, -95.7129), "CA": (56.1304, -106.3468), "GB": (55.3781, -3.4360),
    "DE": (51.1657, 10.4515), "FR": (46.2276, 2.2137), "IT": (41.8719, 12.5674),
    "ES": (40.4637, -3.7492), "NL": (52.1326, 5.2913), "BE": (50.5039, 4.4699),
    "SE": (60.1282, 18.6435), "NO": (60.4720, 8.4689), "DK": (56.2639, 9.5018),
    "FI": (61.9241, 25.7482), "PL": (51.9194, 19.1451), "RU": (61.5240, 105.3188),
    "UA": (48.3794, 31.1656), "IN": (20.5937, 78.9629), "PK": (30.3753, 69.3451),
    "BD": (23.6850, 90.3563), "CN": (35.8617, 104.1954), "JP": (36.2048, 138.2529),
    "KR": (35.9078, 127.7669), "ID": (-0.7893, 113.9213), "MY": (4.2105, 101.9758),
    "SG": (1.3521, 103.8198), "TH": (15.8700, 100.9925), "VN": (14.0583, 108.2772),
    "PH": (12.8797, 121.7740), "AU": (-25.2744, 133.7751), "NZ": (-40.9006, 174.8860),
    "BR": (-14.2350, -51.9253), "AR": (-38.4161, -63.6167), "MX": (23.6345, -102.5528),
    "CL": (-35.6751, -71.5430), "CO": (4.5709, -74.2973), "ZA": (-30.5595, 22.9375),
    "NG": (9.0820, 8.6753), "KE": (-0.0236, 37.9062), "MA": (31.7917, -7.0926),
    "DZ": (28.0339, 1.6596), "TN": (33.8869, 9.5375), "LY": (26.3351, 17.2283),
    "SD": (12.8628, 30.2176), "ET": (9.1450, 40.4897), "GH": (7.9465, -1.0232),
}

TIMEZONE_OFFSET_HINT = {
    "Asia/Baghdad": (33.3, 44.4),
    "Asia/Riyadh": (24.7, 46.7),
    "Asia/Dubai": (25.2, 55.3),
    "Asia/Kuwait": (29.4, 48.0),
    "Asia/Qatar": (25.3, 51.5),
    "Asia/Amman": (31.9, 35.9),
    "Asia/Beirut": (33.9, 35.5),
    "Asia/Damascus": (33.5, 36.3),
    "Asia/Tehran": (35.7, 51.4),
    "Africa/Cairo": (30.0, 31.2),
    "Europe/London": (51.5, -0.1),
    "Europe/Berlin": (52.5, 13.4),
    "Europe/Paris": (48.9, 2.3),
    "America/New_York": (40.7, -74.0),
    "Asia/Karachi": (24.9, 67.0),
    "Asia/Kolkata": (28.6, 77.2),
}

class GeoProvider(Provider):
    name = "geo"
    category = "geo"
    offline = True

    async def run(self, ctx: Context) -> list[Finding]:
        target = ctx.target
        out: list[Finding] = []
        coords: tuple[float, float] | None = None
        precision = "country"
        for tz in target.timezones:
            if tz in TIMEZONE_OFFSET_HINT:
                coords = TIMEZONE_OFFSET_HINT[tz]
                precision = "timezone"
                break
        if coords is None and target.region in COUNTRY_CENTROID:
            coords = COUNTRY_CENTROID[target.region]
        if coords is None:
            return out
        lat, lon = coords
        out.append(self.finding("approx_lat", f"{lat:.4f}", 0.45, "offline-centroid", {"precision": precision}))
        out.append(self.finding("approx_lon", f"{lon:.4f}", 0.45, "offline-centroid", {"precision": precision}))
        out.append(self.finding("precision", precision, 0.6, "offline-centroid"))
        out.append(
            self.finding(
                "map_url",
                f"https://www.google.com/maps?q={lat:.4f},{lon:.4f}",
                0.5,
                "google-maps",
            )
        )
        if target.region_name:
            out.append(self.finding("region_label", target.region_name, 0.7, "libphonenumber"))
        return out