from __future__ import annotations

from providers.eporner import EpornerProvider
from providers.boyfriendtv import BoyfriendtvProvider
from providers.onlygayvideo import OnlyGayVideoProvider
from providers.pornhub import PornhubProvider
from providers.tnaflix import TNAFlixProvider
from providers.xhamster import XHamsterProvider


def available_sites() -> list[str]:
    return ["pornhub", "boyfriendtv", "onlygayvideo", "eporner", "xhamster", "tnaflix"]


def get_provider(site: str):
    normalized = site.strip().lower()
    if normalized == "pornhub":
        return PornhubProvider()
    if normalized == "boyfriendtv":
        return BoyfriendtvProvider()
    if normalized == "onlygayvideo":
        return OnlyGayVideoProvider()
    if normalized == "eporner":
        return EpornerProvider()
    if normalized == "xhamster":
        return XHamsterProvider()
    if normalized == "tnaflix":
        return TNAFlixProvider()
    raise ValueError(f"Unsupported provider: {site}")
