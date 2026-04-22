from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Video:
    title: str
    url: str
    duration_seconds: int | None = None
    views: int | None = None
    is_hd: bool | None = None
    max_quality: int | None = None
    source: str = "pornhub"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
