from __future__ import annotations

import re
from urllib.parse import urlencode

from config import AppSettings
from infrastructure.http_client import HttpClient
from models import Video
from utils import normalize_text, parse_duration_to_seconds, parse_view_count, split_terms

ITEM_PATTERN = re.compile(
    r'<div class="item[^"]*">\s*'
    r'<a href="(?P<href>https://www\.onlygayvideo\.com/videos/[^"]+)" title="(?P<title>[^"]*)"[^>]*>'
    r'(?P<body>.*?)</a>',
    re.S,
)
HD_PATTERN = re.compile(r'<span class="is-hd">HD</span>')
DURATION_PATTERN = re.compile(r'<div class="duration">(?P<duration>[^<]+)</div>')
VIEWS_PATTERN = re.compile(r'<div class="views">(?P<views>[^<]+)</div>')


class OnlyGayVideoProvider:
    name = "onlygayvideo"

    def __init__(self, http_client: HttpClient | None = None, settings: AppSettings | None = None):
        self.settings = settings or AppSettings.from_env()
        self.http_client = http_client or HttpClient(
            retries=self.settings.retries,
            backoff_seconds=self.settings.backoff_seconds,
            request_cookie=self.settings.request_cookie,
            request_proxy=self.settings.request_proxy,
            cookie_domain=".onlygayvideo.com",
        )
        self.http_client.session.headers.update(
            {
                "Referer": "https://www.onlygayvideo.com/",
                "Origin": "https://www.onlygayvideo.com",
                "Sec-Fetch-Site": "same-origin",
            }
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
        _ = (orientation, category, exclude_category, order, period, min_duration, max_duration, hd_only, min_quality)
        normalized_query = normalize_text(query)
        self.http_client.warmup(timeout=timeout, url="https://www.onlygayvideo.com/")
        pages = max_pages or self.settings.default_max_pages
        results = self._collect_pages(
            query=normalized_query,
            timeout=timeout,
            max_pages=pages,
            max_results=max_results,
            progress=progress,
        )
        if post_filter_query:
            results = self._filter_by_query(results, query=normalized_query)
            if progress is not None:
                progress(f"query_relevance_filtered={len(results)}")
        return results

    def _collect_pages(
        self,
        query: str,
        timeout: int,
        max_pages: int,
        max_results: int | None,
        progress,
    ) -> list[Video]:
        dedup: set[str] = set()
        all_videos: list[Video] = []
        for page in range(1, max_pages + 1):
            url = self._search_url(query=query, page=page)
            html = self.http_client.get_text(url, timeout=timeout)
            page_videos = self._extract_videos_from_page_html(html)
            page_videos = [video for video in page_videos if video.url not in dedup]
            if not page_videos:
                break
            if progress is not None:
                progress(f"page={page} found={len(page_videos)}")
            for video in page_videos:
                dedup.add(video.url)
                all_videos.append(video)
            if max_results is not None and len(all_videos) >= max_results:
                return all_videos[:max_results]
        return all_videos

    def _search_url(self, query: str, page: int) -> str:
        params = {"q": query}
        if page > 1:
            params["page"] = page
        return f"https://www.onlygayvideo.com/search/?{urlencode(params)}"

    def _extract_videos_from_page_html(self, html: str) -> list[Video]:
        videos: list[Video] = []
        seen: set[str] = set()
        for match in ITEM_PATTERN.finditer(html):
            url = match.group("href").strip()
            if url in seen:
                continue
            body = match.group("body")
            title = match.group("title").strip() or "Untitled"
            duration_match = DURATION_PATTERN.search(body)
            views_match = VIEWS_PATTERN.search(body)
            videos.append(
                Video(
                    title=title,
                    url=url,
                    duration_seconds=parse_duration_to_seconds(duration_match.group("duration")) if duration_match else None,
                    views=parse_view_count(views_match.group("views")) if views_match else None,
                    is_hd=bool(HD_PATTERN.search(body)),
                    source="onlygayvideo",
                )
            )
            seen.add(url)
        return videos

    def _filter_by_query(self, videos: list[Video], query: str) -> list[Video]:
        terms = split_terms(query)
        if not terms:
            return videos
        out: list[Video] = []
        for video in videos:
            title = video.title.lower()
            if all(term in title for term in terms):
                out.append(video)
        return out
