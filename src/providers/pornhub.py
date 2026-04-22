from __future__ import annotations

from difflib import SequenceMatcher
import re
import time
from urllib.parse import urlencode

from config import AppSettings
from constants import ORDER_TO_QUERY, PERIOD_TO_QUERY
from filters import normalize_orientation
from infrastructure.http_client import HttpClient
from models import Video
from utils import normalize_text, parse_duration_to_seconds, parse_view_count, split_terms

MEDIA_DEFINITION_PATTERN = re.compile(
    r'{("group":\d+,"height":\d+,"width":\d+,)?"defaultQuality":(true|false|\d+),"format":"(\w+)","videoUrl":"(.+?)","quality":(("\d+")|(\[[\d,]*\]))(,"remote":(true|false))?}'
)
VIDEO_LINK_PATTERN = re.compile(r'href="(?P<href>/view_video\.php\?viewkey=[^"]+)"[^>]*')
TITLE_ATTR_PATTERN = re.compile(r'title="(?P<title>[^"]*)"')


class PornhubProvider:
    name = "pornhub"

    def __init__(self, http_client: HttpClient | None = None, settings: AppSettings | None = None):
        self.settings = settings or AppSettings.from_env()
        self.http_client = http_client or HttpClient(
            retries=self.settings.retries,
            backoff_seconds=self.settings.backoff_seconds,
            request_cookie=self.settings.request_cookie,
            request_proxy=self.settings.request_proxy,
        )

    def search_videos(
        self,
        query: str,
        max_results: int | None = None,
        timeout: int = 15,
        progress=None,
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
        post_filter_query: bool = False,
    ) -> list[Video]:
        normalized_query = self._normalized_search_query(query)
        resolved_orientation = self._effective_orientation(orientation, category, normalized_query)
        orientation_query = self._query_with_orientation_prefix(normalized_query, resolved_orientation)
        base = self._search_base_url(resolved_orientation)
        self.http_client.warmup(timeout=timeout)
        pages = max_pages or self.settings.default_max_pages
        results = self._collect_pages(
            base_url=base,
            query=orientation_query,
            timeout=timeout,
            max_pages=pages,
            max_results=max_results,
            order=order,
            period=period,
            category=category,
            exclude_category=exclude_category,
            min_duration=min_duration,
            max_duration=max_duration,
            hd_only=hd_only,
            progress=progress,
        )
        if post_filter_query:
            results = self._filter_by_query(results, query=normalized_query, progress=progress, strict=True)
            if progress is not None:
                progress(f"query_relevance_filtered={len(results)}")
        if min_quality is not None:
            results = self._filter_by_quality(results, min_quality=min_quality, timeout=timeout)
        return results

    def _collect_pages(
        self,
        base_url: str,
        query: str,
        timeout: int,
        max_pages: int,
        max_results: int | None,
        order: str | None,
        period: str | None,
        category: str | None,
        exclude_category: str | None,
        min_duration: int | None,
        max_duration: int | None,
        hd_only: bool,
        progress,
    ) -> list[Video]:
        dedup: set[str] = set()
        all_videos: list[Video] = []
        for page in range(1, max_pages + 1):
            url = self._search_url(
                base_url,
                query,
                page,
                order=order,
                period=period,
                filter_category=self._safe_int(category),
                exclude_category=exclude_category,
                min_duration=min_duration,
                max_duration=max_duration,
                hd_only=hd_only,
            )
            page_started_at = time.perf_counter()
            fetch_started_at = time.perf_counter()
            html = self.http_client.get_text(url, timeout=timeout)
            fetch_elapsed_ms = int((time.perf_counter() - fetch_started_at) * 1000)
            parse_started_at = time.perf_counter()
            page_videos = self._extract_videos_from_page_html(html)
            parse_elapsed_ms = int((time.perf_counter() - parse_started_at) * 1000)
            page_videos = [v for v in page_videos if v.url not in dedup]
            if not page_videos:
                if progress is not None:
                    page_elapsed_ms = int((time.perf_counter() - page_started_at) * 1000)
                    progress(
                        f"page={page} found=0 fetch_ms={fetch_elapsed_ms} "
                        f"parse_ms={parse_elapsed_ms} total_ms={page_elapsed_ms}"
                    )
                break
            if progress is not None:
                page_elapsed_ms = int((time.perf_counter() - page_started_at) * 1000)
                progress(
                    f"page={page} found={len(page_videos)} fetch_ms={fetch_elapsed_ms} "
                    f"parse_ms={parse_elapsed_ms} total_ms={page_elapsed_ms}"
                )
            for video in page_videos:
                dedup.add(video.url)
                all_videos.append(video)
            if max_results is not None and len(all_videos) >= max_results:
                return all_videos[:max_results]
        return all_videos

    def _filter_by_quality(self, videos: list[Video], min_quality: int, timeout: int) -> list[Video]:
        enriched: list[Video] = []
        for video in videos:
            max_quality = self._extract_max_quality(video.url, timeout=timeout)
            if max_quality < min_quality:
                continue
            enriched.append(
                Video(
                    title=video.title,
                    url=video.url,
                    duration_seconds=video.duration_seconds,
                    views=video.views,
                    is_hd=max_quality >= 720,
                    max_quality=max_quality,
                    source=video.source,
                )
            )
        return enriched

    def _extract_max_quality(self, url: str, timeout: int) -> int:
        html = self.http_client.get_text(url, timeout=timeout)
        max_quality = 0
        for match in MEDIA_DEFINITION_PATTERN.finditer(html):
            raw_quality = match.group(6)
            max_quality = max(max_quality, self._parse_quality_value(raw_quality))
        return max_quality

    def _parse_quality_value(self, raw_quality: str) -> int:
        if raw_quality.startswith("["):
            values = [int(part) for part in re.findall(r"\d+", raw_quality)]
            return max(values) if values else 0
        values = [int(part) for part in re.findall(r"\d+", raw_quality)]
        return values[0] if values else 0

    def _safe_int(self, value: str | None) -> int | None:
        if value is None:
            return None
        return int(value) if str(value).isdigit() else None

    def _search_base_url(self, orientation: str | None) -> str:
        _ = orientation
        return "https://www.pornhub.com/video/search"

    def _query_with_orientation_prefix(self, query: str, orientation: str) -> str:
        prefix_by_orientation = {
            "straight": "straight",
            "gay": "gay",
            "lesbian": "lesbian",
            "transgender": "transgender",
        }
        prefix = prefix_by_orientation.get(orientation, "")
        if not prefix:
            return query
        terms = split_terms(query)
        if prefix in terms:
            return query
        return f"{prefix} {query}".strip()

    def _search_url(
        self,
        base_url: str,
        query: str,
        page: int,
        filter_category: int | None = None,
        order: str | None = None,
        period: str | None = None,
        exclude_category: str | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
        hd_only: bool = False,
    ) -> str:
        params: dict[str, object] = {"search": query, "page": page}
        self._attach_optional_params(
            params,
            filter_category=filter_category,
            order=order,
            period=period,
            exclude_category=exclude_category,
            min_duration=min_duration,
            max_duration=max_duration,
            hd_only=hd_only,
        )
        return f"{base_url}?{urlencode(params, doseq=True)}"

    def _attach_optional_params(
        self,
        params: dict[str, object],
        filter_category: int | None,
        order: str | None,
        period: str | None,
        exclude_category: str | None,
        min_duration: int | None,
        max_duration: int | None,
        hd_only: bool,
    ) -> None:
        if filter_category is not None:
            params["filter_category"] = filter_category
        if exclude_category:
            params["exclude_category"] = exclude_category
        if min_duration is not None:
            params["min_duration"] = min_duration
        if max_duration is not None:
            params["max_duration"] = max_duration
        if hd_only:
            params["hd"] = "1"
        sort_code = ORDER_TO_QUERY.get((order or "").lower())
        if sort_code:
            params["o"] = sort_code
        period_code = PERIOD_TO_QUERY.get((period or "").lower())
        if period_code and sort_code in {"mv", "tr"}:
            params["t"] = period_code

    def _effective_orientation(self, orientation: str | None, category: str | None = None, query: str | None = None) -> str:
        normalized = normalize_orientation(orientation)
        if normalized in {"straight", "gay", "lesbian", "transgender"}:
            return normalized
        category_key = (category or "").strip().lower()
        if category_key == "gay":
            return "gay"
        if category_key in {"lesbian", "lesbo"}:
            return "lesbian"
        lowered_query = f" {(query or '').lower()} "
        if " gay " in lowered_query:
            return "gay"
        if " lesbian " in lowered_query or " lesbo " in lowered_query:
            return "lesbian"
        if normalized in {"bi", "any"}:
            return "straight"
        return "gay"

    def _normalized_search_query(self, query: str) -> str:
        return normalize_text(query)

    def _filter_by_query(self, videos: list[Video], query: str, progress=None, strict: bool = False) -> list[Video]:
        terms = split_terms(query)
        if not terms:
            return videos
        threshold = 2 if len(terms) > 1 else 1
        if strict and len(terms) > 2:
            threshold = len(terms) - 1
        scored = self._score_videos(videos, terms)
        selected = [video for score, _, video in scored if score >= threshold]
        if selected or strict:
            return selected
        return [video for score, _, video in scored if score >= 1]

    def _score_videos(self, videos: list[Video], terms: list[str]) -> list[tuple[int, int, Video]]:
        scored: list[tuple[int, int, Video]] = []
        for index, video in enumerate(videos):
            title_tokens = split_terms(video.title)
            score = sum(1 for term in terms if self._term_matches_title(term, title_tokens))
            scored.append((score, index, video))
        return sorted(scored, key=lambda item: (-item[0], item[1]))

    def _term_matches_title(self, term: str, title_tokens: list[str]) -> bool:
        if not title_tokens:
            return False
        for token in title_tokens:
            if term == token:
                return True
            if len(term) >= 4 and term in token:
                return True
            if len(token) >= 4 and token in term:
                return True
            if self._is_close_match(term, token):
                return True
        return False

    def _is_close_match(self, left: str, right: str) -> bool:
        if abs(len(left) - len(right)) > 2:
            return False
        ratio = SequenceMatcher(a=left, b=right).ratio()
        return ratio >= 0.84

    def _video_from_webmaster_item(self, item: dict[str, object]) -> Video | None:
        url = str(item.get("url") or "")
        title = str(item.get("title") or "").strip()
        if not url or not title:
            return None
        duration = parse_duration_to_seconds(str(item.get("duration") or ""))
        views = parse_view_count(str(item.get("views") or ""))
        return Video(title=title, url=url, duration_seconds=duration, views=views)

    def _extract_videos_from_page_html(self, html: str) -> list[Video]:
        videos: list[Video] = []
        seen: set[str] = set()
        for match in VIDEO_LINK_PATTERN.finditer(html):
            href = match.group("href")
            absolute = f"https://www.pornhub.com{href}" if href.startswith("/") else href
            if absolute in seen:
                continue
            tail = html[match.start() : match.end() + 200]
            title_match = TITLE_ATTR_PATTERN.search(tail)
            title = title_match.group("title").strip() if title_match else "Untitled"
            videos.append(Video(title=title or "Untitled", url=absolute))
            seen.add(absolute)
        return videos
