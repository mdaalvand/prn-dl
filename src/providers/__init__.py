from __future__ import annotations

from providers.boyfriendtv import BoyfriendtvProvider
from providers.pornhub import PornhubProvider


def available_sites() -> list[str]:
    return ["pornhub", "boyfriendtv"]


def get_provider(site: str):
    normalized = site.strip().lower()
    if normalized == "pornhub":
        return PornhubProvider()
    if normalized == "boyfriendtv":
        return BoyfriendtvProvider()
    raise ValueError(f"Unsupported provider: {site}")
