from argparse import Namespace
import json

from cli import _run_download, build_parser
from models import Video
from status import PipelineReporter
from providers import available_sites, get_provider


def test_default_provider_registered() -> None:
    sites = available_sites()
    assert "pornhub" in sites
    assert "boyfriendtv" in sites
    assert "onlygayvideo" in sites
    assert "eporner" in sites
    assert "xhamster" in sites
    assert "tnaflix" in sites
    provider = get_provider("pornhub")
    assert provider.name == "pornhub"
    btv_provider = get_provider("boyfriendtv")
    assert btv_provider.name == "boyfriendtv"
    ogv_provider = get_provider("onlygayvideo")
    assert ogv_provider.name == "onlygayvideo"
    eporner_provider = get_provider("eporner")
    assert eporner_provider.name == "eporner"
    xhamster_provider = get_provider("xhamster")
    assert xhamster_provider.name == "xhamster"
    tnaflix_provider = get_provider("tnaflix")
    assert tnaflix_provider.name == "tnaflix"


def test_download_default_quality_is_480() -> None:
    parser = build_parser()
    args = parser.parse_args(["download", "demo query"])
    assert args.quality == 480


def test_search_accepts_max_pages() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--max-pages", "3", "--json"])
    assert args.max_pages == 3


def test_search_accepts_orientation_filter() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--orientation", "bi"])
    assert args.orientation == "bi"


def test_search_accepts_site_selection() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--site", "boyfriendtv"])
    assert args.site == "boyfriendtv"


def test_search_accepts_new_site_selection() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--site", "xhamster"])
    assert args.site == "xhamster"


def test_direct_download_accepts_site_selection() -> None:
    parser = build_parser()
    args = parser.parse_args(["direct-download", "--site", "boyfriendtv", "--url", "https://example.com/v"])
    assert args.site == "boyfriendtv"


def test_direct_download_accepts_new_site_selection() -> None:
    parser = build_parser()
    args = parser.parse_args(["direct-download", "--site", "tnaflix", "--url", "https://example.com/v"])
    assert args.site == "tnaflix"


def test_search_accepts_category() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--category", "gay"])
    assert args.category == "gay"


def test_search_accepts_optional_query_post_filter_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--post-filter-query"])
    assert args.post_filter_query is True


def test_download_accepts_page_url_multiple_times() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "download",
            "demo",
            "--page-url",
            "https://www.pornhub.com/video/search?search=demo",
            "--page-url",
            "https://www.pornhub.com/gay/video/search?search=demo",
        ]
    )
    assert args.page_url == [
        "https://www.pornhub.com/video/search?search=demo",
        "https://www.pornhub.com/gay/video/search?search=demo",
    ]


def test_download_dry_run_with_json_keeps_stdout_clean(capsys) -> None:
    args = Namespace(
        dry_run=True,
        json=True,
        quality=720,
        audio_only=False,
        timeout=10,
        output="downloads",
    )
    reporter = PipelineReporter(enabled=False)
    videos = [Video(title="x", url="u1")]

    code = _run_download(args, videos, reporter)

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert "Dry-run enabled. Skipping download." in captured.err


def test_download_json_output_contains_context_and_reasons(monkeypatch, capsys) -> None:
    class FakeDownloader:
        def __init__(
            self,
            retries: int,
            backoff_seconds: float,
            request_cookie: str = "",
            request_proxy: str = "",
            user_agent: str = "",
            impersonate_target: str = "",
        ) -> None:
            _ = (retries, backoff_seconds, request_cookie, request_proxy, user_agent, impersonate_target)

        def download_batch(self, videos, output_dir, quality, audio_only, timeout):
            _ = (videos, output_dir, quality, audio_only, timeout)
            from infrastructure.downloader import DownloadResult
            return DownloadResult(succeeded=["u1"], failed=["u2"], failures={"u2": "timeout_after_300s"})

    monkeypatch.setattr("cli.YtDlpDownloader", FakeDownloader)

    args = Namespace(
        dry_run=False,
        json=True,
        quality=720,
        audio_only=False,
        timeout=45,
        output="downloads",
    )
    reporter = PipelineReporter(enabled=False)
    videos = [Video(title="ok", url="u1"), Video(title="fail", url="u2")]

    code = _run_download(args, videos, reporter)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["succeeded"] == ["u1"]
    assert payload["failed"] == ["u2"]
    assert payload["failure_reasons"]["u2"] == "timeout_after_300s"
    assert payload["download_context"]["timeout"] == 45


def test_download_returns_error_only_when_all_items_fail(monkeypatch, capsys) -> None:
    class FakeDownloader:
        def __init__(
            self,
            retries: int,
            backoff_seconds: float,
            request_cookie: str = "",
            request_proxy: str = "",
            user_agent: str = "",
            impersonate_target: str = "",
        ) -> None:
            _ = (retries, backoff_seconds, request_cookie, request_proxy, user_agent, impersonate_target)

        def download_batch(self, videos, output_dir, quality, audio_only, timeout):
            _ = (videos, output_dir, quality, audio_only, timeout)
            from infrastructure.downloader import DownloadResult
            return DownloadResult(succeeded=[], failed=["u1", "u2"], failures={"u1": "e1", "u2": "e2"})

    monkeypatch.setattr("cli.YtDlpDownloader", FakeDownloader)

    args = Namespace(
        dry_run=False,
        json=True,
        quality=480,
        audio_only=False,
        timeout=45,
        output="downloads",
    )
    reporter = PipelineReporter(enabled=False)
    videos = [Video(title="a", url="u1"), Video(title="b", url="u2")]

    code = _run_download(args, videos, reporter)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 1
    assert payload["succeeded"] == []
    assert payload["failed"] == ["u1", "u2"]


def test_boyfriendtv_direct_download_resolves_page_urls(monkeypatch, capsys) -> None:
    class FakeResolver:
        def __init__(self, *args, **kwargs) -> None:
            _ = (args, kwargs)

        def resolve_download_urls(self, urls, timeout):
            _ = timeout
            return [f"{url}?resolved=1" for url in urls]

    class FakeDownloader:
        def __init__(
            self,
            retries: int,
            backoff_seconds: float,
            request_cookie: str = "",
            request_proxy: str = "",
            user_agent: str = "",
            impersonate_target: str = "",
        ) -> None:
            _ = (retries, backoff_seconds, request_cookie, request_proxy, user_agent, impersonate_target)
            self.downloaded_urls = []

        def download_batch(self, videos, output_dir, quality, audio_only, timeout):
            _ = (output_dir, quality, audio_only, timeout)
            self.downloaded_urls = [video.url for video in videos]
            from infrastructure.downloader import DownloadResult
            return DownloadResult(succeeded=self.downloaded_urls, failed=[], failures={})

    monkeypatch.setattr("cli.BoyfriendtvProvider", FakeResolver)
    monkeypatch.setattr("cli.YtDlpDownloader", FakeDownloader)

    args = Namespace(
        dry_run=False,
        json=True,
        quality=480,
        audio_only=False,
        timeout=45,
        output="downloads",
        site="boyfriendtv",
    )
    reporter = PipelineReporter(enabled=False)
    videos = [Video(title="a", url="https://www.boyfriendtv.com/videos/one")]

    code = _run_download(args, videos, reporter)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["succeeded"] == ["https://www.boyfriendtv.com/videos/one?resolved=1"]
