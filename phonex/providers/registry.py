from __future__ import annotations

from typing import Iterable

from .base import Provider
from .breach import BreachProvider
from .hlr import HlrProvider
from .ip_geo import IpGeoProvider
from .mccmnc import MccMncProvider
from .messaging import MessagingProvider
from .number_meta import NumberMetaProvider
from .social_dorks import SocialDorksProvider

_REGISTRY: dict[str, type[Provider]] = {
    NumberMetaProvider.name: NumberMetaProvider,
    MccMncProvider.name: MccMncProvider,
    MessagingProvider.name: MessagingProvider,
    SocialDorksProvider.name: SocialDorksProvider,
    HlrProvider.name: HlrProvider,
    BreachProvider.name: BreachProvider,
    IpGeoProvider.name: IpGeoProvider,
}


def available() -> list[str]:
    return sorted(_REGISTRY)


def build(names: Iterable[str] | None = None) -> list[Provider]:
    selected = list(names) if names else available()
    out: list[Provider] = []
    for name in selected:
        cls = _REGISTRY.get(name)
        if cls is not None:
            out.append(cls())
    return out