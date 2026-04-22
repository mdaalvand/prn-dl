from models import Video
from pipeline import SearchOptions, run_search_pipeline
from status import PipelineReporter


class FakeProvider:
    name = "fake"

    def search_videos(
        self,
        query: str,
        max_results=None,
        timeout: int = 15,
        progress=None,
        max_pages: int | None = None,
        orientation: str | None = None,
        category: str | None = None,
    ) -> list[Video]:
        if progress is not None:
            progress("fake search started")
        return [
            Video(title="alpha hd", url="u1", duration_seconds=120, views=3000, is_hd=True),
            Video(title="beta", url="u2", duration_seconds=360, views=9000, is_hd=False),
            Video(title="gamma hd", url="u3", duration_seconds=80, views=1000, is_hd=True),
        ]


def test_run_search_pipeline_filters_sorts_and_limits() -> None:
    provider = FakeProvider()
    reporter = PipelineReporter(enabled=False)
    options = SearchOptions(
        query="demo",
        timeout=5,
        min_duration=100,
        max_duration=None,
        min_views=2000,
        hd_only=True,
        title_contains=None,
        orientation="any",
        category=None,
        sort_by="views",
        count=1,
        max_pages=5,
    )

    out = run_search_pipeline(provider, options, reporter)
    assert len(out) == 1
    assert out[0].url == "u1"
