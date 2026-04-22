from __future__ import annotations

from typing import Protocol

from models import Video


class VideoProvider(Protocol):
    name: str

    def search_videos(
        self,
        query: str,
        max_results: int | None = None,
        timeout: int = 15,
        progress: callable | None = None,
        max_pages: int | None = None,
        orientation: str | None = None,
        category: str | None = None,
        exclude_category: str | None = None,
        order: str | None = None,
        period: str | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
        hd_only: bool = False,
        min_quality: int | None = None,
    ) -> list[Video]: ...
