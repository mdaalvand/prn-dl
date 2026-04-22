from __future__ import annotations

from collections.abc import Iterable

from constants import ORIENTATION_ALIASES
from models import Video
from utils import split_terms


def normalize_orientation(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower()
    return ORIENTATION_ALIASES.get(key)


def _matches_terms(title: str, terms: Iterable[str]) -> bool:
    terms_list = list(terms)
    if not terms_list:
        return True
    lowered = title.lower()
    return all(term in lowered for term in terms_list)


def _matches_excluded_terms(title: str, terms: Iterable[str]) -> bool:
    terms_list = list(terms)
    if not terms_list:
        return False
    lowered = title.lower()
    return any(term in lowered for term in terms_list)


def apply_filters(
    videos: list[Video],
    min_duration: int | None = None,
    max_duration: int | None = None,
    min_views: int | None = None,
    hd_only: bool = False,
    min_quality: int | None = None,
    title_contains: str | None = None,
    include_terms: str | None = None,
    exclude_terms: str | None = None,
    orientation: str | None = None,
) -> list[Video]:
    _ = normalize_orientation(orientation)
    include = split_terms(include_terms or title_contains)
    exclude = split_terms(exclude_terms)
    result: list[Video] = []
    for video in videos:
        if min_duration is not None and (video.duration_seconds or 0) < min_duration:
            continue
        if max_duration is not None and (video.duration_seconds or 0) > max_duration:
            continue
        if min_views is not None and (video.views or 0) < min_views:
            continue
        if hd_only and not bool(video.is_hd):
            continue
        if min_quality is not None and (video.max_quality or 0) < min_quality:
            continue
        if not _matches_terms(video.title, include):
            continue
        if _matches_excluded_terms(video.title, exclude):
            continue
        result.append(video)
    return result


def sort_videos(videos: list[Video], by: str = "relevance") -> list[Video]:
    if by == "views":
        return sorted(videos, key=lambda v: (v.views or 0), reverse=True)
    if by == "duration":
        return sorted(videos, key=lambda v: (v.duration_seconds or 0), reverse=True)
    if by == "quality":
        return sorted(videos, key=lambda v: (v.max_quality or 0), reverse=True)
    return list(videos)
