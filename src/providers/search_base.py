from __future__ import annotations

import re
from typing import Callable
from urllib.parse import urljoin

from config import AppSettings
from infrastructure.http_client import HttpClient
from models import Video
from utils import normalize_text, split_terms


class SearchPageProvider:
    name: str = ""
    source: str = ""
    home_url: str = ""
    cookie_domain: str = ""
    result_link_pattern: re.Pattern[str]

    def __init__(self, http_client: HttpClient | None = None, settings: AppSettings | None = None):
        self.settings = settings or AppSettings.from_env()
        self.http_client = http_client or HttpClient(
            retries=self.settings.retries,
            backoff_seconds=self.settings.backoff_seconds,
            request_cookie=self.settings.request_cookie,
            request_proxy=self.settings.request_proxy,
            cookie_domain=self.cookie_domain,
        )
        self.http_client.session.headers.update(
            {
                "Referer": self.home_url,
                "Origin": self.home_url.rstrip("/"),
                "Sec-Fetch-Site": "same-origin",
            }
        )

    def search_videos(
        self,
        query: str,
        max_results: int | None = None,
        timeout: int = 15,
        progress: Callable[[str], None] | None = None,
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
        self.http_client.warmup(timeout=timeout, url=self.home_url)
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
        progress: Callable[[str], None] | None,
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
        raise NotImplementedError

    def _extract_videos_from_page_html(self, html: str) -> list[Video]:
        videos: list[Video] = []
        seen: set[str] = set()
        for match in self.result_link_pattern.finditer(html):
            href = match.group("href").strip()
            absolute = urljoin(self.home_url, href)
            if absolute in seen:
                continue
            tail = html[match.start() : match.end() + 260]
            title = self._extract_title(tail)
            videos.append(Video(title=title, url=absolute, source=self.source))
            seen.add(absolute)
        return videos

    def _extract_title(self, snippet: str) -> str:
        for pattern in (
            r'title="(?P<title>[^"]*)"',
            r'aria-label="(?P<title>[^"]*)"',
            r'data-title="(?P<title>[^"]*)"',
        ):
            match = re.search(pattern, snippet)
            if match:
                title = match.group("title").strip()
                if title:
                    return title
        return "Untitled"

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
