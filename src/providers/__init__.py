from __future__ import annotations

from providers.pornhub import PornhubProvider


def available_sites() -> list[str]:
    return ["pornhub"]


def get_provider(site: str):
    normalized = site.strip().lower()
    if normalized == "pornhub":
        return PornhubProvider()
    raise ValueError(f"Unsupported provider: {site}")
