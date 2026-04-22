from __future__ import annotations

import inspect
import time
from dataclasses import dataclass

from filters import apply_filters, sort_videos
from models import Video
from selection import select_videos
from status import PipelineReporter


@dataclass(frozen=True)
class SearchOptions:
    query: str
    timeout: int
    count: int
    pool_size: int = 100
    mode: str = "top"
    seed: int | None = None
    order: str = "most_relevant"
    period: str = "alltime"
    orientation: str = "gay"
    category: str | None = None
    exclude_category: str | None = None
    min_duration: int | None = None
    max_duration: int | None = None
    min_quality: int | None = None
    hd_only: bool = False
    min_views: int | None = None
    include_terms: str | None = None
    exclude_terms: str | None = None
    max_pages: int = 3
    title_contains: str | None = None
    sort_by: str = "relevance"
    post_filter_query: bool = False


def run_search_pipeline(provider, options: SearchOptions, reporter: PipelineReporter) -> list[Video]:
    started_at = time.perf_counter()
    reporter.event("search_started", provider=getattr(provider, "name", "unknown"))
    fetch_started_at = time.perf_counter()
    fetched = provider.search_videos(**_provider_kwargs(provider, options, reporter))
    fetch_elapsed_ms = int((time.perf_counter() - fetch_started_at) * 1000)
    reporter.event("search_stage_timing", stage="provider_fetch", elapsed_ms=fetch_elapsed_ms, fetched=len(fetched))

    filter_started_at = time.perf_counter()
    filtered = apply_filters(
        fetched,
        min_duration=options.min_duration,
        max_duration=options.max_duration,
        min_views=options.min_views,
        hd_only=options.hd_only,
        min_quality=options.min_quality,
        title_contains=options.title_contains,
        include_terms=options.include_terms,
        exclude_terms=options.exclude_terms,
        orientation=options.orientation,
    )
    filter_elapsed_ms = int((time.perf_counter() - filter_started_at) * 1000)
    reporter.event("search_stage_timing", stage="filter", elapsed_ms=filter_elapsed_ms, filtered=len(filtered))

    sort_started_at = time.perf_counter()
    ordered = sort_videos(filtered, by=options.sort_by)
    sort_elapsed_ms = int((time.perf_counter() - sort_started_at) * 1000)
    reporter.event("search_stage_timing", stage="sort", elapsed_ms=sort_elapsed_ms, ordered=len(ordered))

    select_started_at = time.perf_counter()
    selected = select_videos(
        ordered,
        limit=options.count,
        pool_size=options.pool_size,
        mode=options.mode,
        seed=options.seed,
    )
    select_elapsed_ms = int((time.perf_counter() - select_started_at) * 1000)
    total_elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    reporter.event("search_stage_timing", stage="select", elapsed_ms=select_elapsed_ms, selected=len(selected))
    reporter.event(
        "search_finished",
        fetched=len(fetched),
        filtered=len(filtered),
        selected=len(selected),
        elapsed_ms=total_elapsed_ms,
    )
    return selected


def _provider_kwargs(provider, options: SearchOptions, reporter: PipelineReporter) -> dict[str, object]:
    payload: dict[str, object] = {
        "query": options.query,
        "max_results": max(options.pool_size, options.count),
        "timeout": options.timeout,
        "progress": lambda msg: reporter.event("provider_progress", detail=msg),
        "max_pages": options.max_pages,
        "orientation": options.orientation,
        "category": options.category,
        "exclude_category": options.exclude_category,
        "order": options.order,
        "period": options.period,
        "min_duration": options.min_duration,
        "max_duration": options.max_duration,
        "hd_only": options.hd_only,
        "min_quality": options.min_quality,
        "post_filter_query": options.post_filter_query,
    }
    accepted = set(inspect.signature(provider.search_videos).parameters)
    return {key: value for key, value in payload.items() if key in accepted}
