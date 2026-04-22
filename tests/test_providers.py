from argparse import Namespace

from cli import _run_download, build_parser
from models import Video
from status import PipelineReporter
from providers import available_sites, get_provider


def test_default_provider_registered() -> None:
    sites = available_sites()
    assert "pornhub" in sites
    provider = get_provider("pornhub")
    assert provider.name == "pornhub"


def test_download_default_quality_is_medium_720() -> None:
    parser = build_parser()
    args = parser.parse_args(["download", "demo query"])
    assert args.quality == 720


def test_search_accepts_max_pages() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--max-pages", "3", "--json"])
    assert args.max_pages == 3


def test_search_accepts_orientation_filter() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--orientation", "bi"])
    assert args.orientation == "bi"


def test_search_accepts_category() -> None:
    parser = build_parser()
    args = parser.parse_args(["search", "demo", "--category", "gay"])
    assert args.category == "gay"


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
