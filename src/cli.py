from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace

from config import AppSettings
from errors import HttpRequestError
from infrastructure.downloader import YtDlpDownloader
from logging_utils import configure_logging
from models import Video
from pipeline import SearchOptions, run_search_pipeline
from providers import get_provider
from status import PipelineReporter


def build_parser() -> argparse.ArgumentParser:
    settings = AppSettings()
    parser = argparse.ArgumentParser(prog="phfetch", description="Search and download videos with filters.")
    parser.add_argument("--log-level", default="INFO")

    sub = parser.add_subparsers(dest="command", required=True)
    _build_search_subparser(sub, settings)
    _build_download_subparser(sub, settings)
    _build_direct_subparser(sub, settings)
    return parser


def _build_search_subparser(subparsers, settings: AppSettings) -> None:
    parser = subparsers.add_parser("search", help="Search videos only")
    _add_query_args(parser)
    _add_filter_args(parser, settings)
    parser.add_argument("--json", action="store_true")


def _build_download_subparser(subparsers, settings: AppSettings) -> None:
    parser = subparsers.add_parser("download", help="Search then download")
    _add_query_args(parser)
    _add_filter_args(parser, settings)
    _add_download_args(parser, settings)
    parser.add_argument("--page-url", action="append", default=[])


def _build_direct_subparser(subparsers, settings: AppSettings) -> None:
    parser = subparsers.add_parser("direct-download", help="Download provided URLs")
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--urls-file")
    _add_download_args(parser, settings)


def _add_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("query", nargs="?", default=None)
    parser.add_argument("--query", dest="query_flag", default=None)


def _add_filter_args(parser: argparse.ArgumentParser, settings: AppSettings) -> None:
    parser.add_argument("--limit", type=int, default=settings.default_limit)
    parser.add_argument("--pool-size", type=int, default=settings.default_pool_size)
    parser.add_argument("--mode", choices=["top", "random"], default=settings.default_mode)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--order", default="most_relevant")
    parser.add_argument("--period", default="alltime")
    parser.add_argument("--orientation", default="straight")
    parser.add_argument("--category")
    parser.add_argument("--exclude-category")
    parser.add_argument("--min-duration", type=int)
    parser.add_argument("--max-duration", type=int)
    parser.add_argument("--min-quality", type=int)
    parser.add_argument("--hd-only", action="store_true")
    parser.add_argument("--min-views", type=int)
    parser.add_argument("--include-terms")
    parser.add_argument("--exclude-terms")
    parser.add_argument("--max-pages", type=int, default=settings.default_max_pages)
    parser.add_argument("--post-filter-query", action="store_true")


def _add_download_args(parser: argparse.ArgumentParser, settings: AppSettings) -> None:
    parser.add_argument("--quality", type=int, default=settings.default_quality)
    parser.add_argument("--output", default=settings.default_output_dir)
    parser.add_argument("--audio-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=settings.timeout_seconds)
    parser.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    reporter = PipelineReporter(enabled=True, json_output=getattr(args, "json", False))
    try:
        if args.command == "search":
            return _run_search_command(args, reporter)
        if args.command == "download":
            return _run_search_download_command(args, reporter)
        if args.command == "direct-download":
            return _run_direct_download_command(args, reporter)
        parser.error(f"Unknown command: {args.command}")
        return 2
    except HttpRequestError as exc:
        return _handle_http_request_error(args, exc)


def _resolve_query(args: Namespace) -> str:
    query = args.query_flag or args.query
    if not query:
        raise ValueError("query is required. Use positional value or --query.")
    return query


def _build_search_options(args: Namespace, query: str) -> SearchOptions:
    return SearchOptions(
        query=query,
        timeout=args.timeout if hasattr(args, "timeout") else AppSettings.from_env().timeout_seconds,
        count=args.limit,
        pool_size=args.pool_size,
        mode=args.mode,
        seed=args.seed,
        order=args.order,
        period=args.period,
        orientation=args.orientation,
        category=args.category,
        exclude_category=args.exclude_category,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        min_quality=args.min_quality,
        hd_only=args.hd_only,
        min_views=args.min_views,
        include_terms=args.include_terms,
        exclude_terms=args.exclude_terms,
        max_pages=args.max_pages,
        sort_by=_sort_key_from_order(args.order),
        title_contains=args.include_terms,
        post_filter_query=args.post_filter_query,
    )


def _sort_key_from_order(order: str) -> str:
    order_map = {
        "most_viewed": "views",
        "top_rated": "views",
    }
    return order_map.get(order, "relevance")


def _run_search_command(args: Namespace, reporter: PipelineReporter) -> int:
    try:
        query = _resolve_query(args)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    provider = get_provider("pornhub")
    options = _build_search_options(args, query)
    videos = run_search_pipeline(provider, options, reporter)
    _write_results(videos, json_output=args.json)
    return 0


def _run_search_download_command(args: Namespace, reporter: PipelineReporter) -> int:
    try:
        query = _resolve_query(args)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    provider = get_provider("pornhub")
    options = _build_search_options(args, query)
    videos = run_search_pipeline(provider, options, reporter)
    _write_results(videos, json_output=args.json)
    return _run_download(args, videos, reporter)


def _run_direct_download_command(args: Namespace, reporter: PipelineReporter) -> int:
    urls = _collect_direct_urls(args)
    videos = [Video(title=f"video-{idx + 1}", url=url) for idx, url in enumerate(urls)]
    return _run_download(args, videos, reporter)


def _collect_direct_urls(args: Namespace) -> list[str]:
    urls = [url for url in args.url if url]
    if args.urls_file:
        with open(args.urls_file, "r", encoding="utf-8") as handle:
            urls.extend(line.strip() for line in handle if line.strip())
    dedup: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        dedup.append(url)
    return dedup


def _write_results(videos: list[Video], json_output: bool) -> None:
    if json_output:
        data = [video.to_dict() for video in videos]
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return
    for idx, video in enumerate(videos, start=1):
        sys.stdout.write(f"{idx}. {video.title} | {video.url}\n")


def _run_download(args: Namespace, videos: list[Video], reporter: PipelineReporter) -> int:
    if args.dry_run:
        sys.stderr.write("Dry-run enabled. Skipping download.\n")
        return 0
    reporter.event(
        "download_started",
        total=len(videos),
        quality=args.quality,
        timeout=args.timeout,
        output=args.output,
        audio_only=args.audio_only,
    )
    settings = AppSettings.from_env()
    downloader = YtDlpDownloader(retries=settings.retries, backoff_seconds=settings.backoff_seconds)
    result = downloader.download_batch(
        videos,
        output_dir=args.output,
        quality=args.quality,
        audio_only=args.audio_only,
        timeout=args.timeout,
    )
    reporter.event("download_finished", succeeded=len(result.succeeded), failed=len(result.failed))
    if args.json:
        payload = {
            "succeeded": result.succeeded,
            "failed": result.failed,
            "failure_reasons": result.failures,
            "download_context": {
                "quality": args.quality,
                "timeout": args.timeout,
                "output": args.output,
                "audio_only": args.audio_only,
            },
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0 if not result.failed else 1


def _handle_http_request_error(args: Namespace, exc: HttpRequestError) -> int:
    payload = {
        "error": {
            "type": "http_request_error",
            "method": exc.method,
            "url": exc.url,
            "status_code": exc.status_code,
            "attempts": exc.attempts,
            "reason": exc.reason,
            "hint": (
                "Provider blocked request (often datacenter IP / anti-bot 403). "
                "Try self-hosted runner, proxy, or authenticated cookies."
            ),
        },
        "request_context": {
            "query": getattr(args, "query_flag", None) or getattr(args, "query", None),
            "orientation": getattr(args, "orientation", None),
            "category": getattr(args, "category", None),
            "order": getattr(args, "order", None),
            "period": getattr(args, "period", None),
            "timeout": getattr(args, "timeout", None),
            "cookie_configured": bool(AppSettings.from_env().request_cookie),
            "proxy_configured": bool(AppSettings.from_env().request_proxy),
        },
    }
    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stderr.write(
            f"HTTP request failed: {exc.method} {exc.url} | status={exc.status_code} "
            f"attempts={exc.attempts} reason={exc.reason}\n"
        )
    return 1
