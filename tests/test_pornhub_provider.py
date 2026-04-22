from models import Video
from providers.pornhub import PornhubProvider


def test_filter_by_query_prefers_stronger_multi_token_matches() -> None:
    provider = PornhubProvider()
    videos = [
        Video(title="Hot gay teen scene", url="u1"),
        Video(title="Latino outdoor fun", url="u2"),
        Video(title="Completely unrelated title", url="u3"),
    ]

    out = provider._filter_by_query(videos, query="gay teen latino", progress=None, strict=False)

    assert [video.url for video in out] == ["u1"]


def test_filter_by_query_uses_stricter_threshold_for_strict_mode() -> None:
    provider = PornhubProvider()
    videos = [
        Video(title="gay teen party", url="u1"),
        Video(title="gay only title", url="u2"),
    ]

    out = provider._filter_by_query(videos, query="gay teen latino", progress=None, strict=True)

    assert [video.url for video in out] == ["u1"]


def test_filter_by_query_strict_tolerates_small_typo_in_term() -> None:
    provider = PornhubProvider()
    videos = [
        Video(title="Angel Rivera interview", url="u1"),
        Video(title="Angel unrelated title", url="u2"),
    ]

    out = provider._filter_by_query(videos, query="angel reivera", progress=None, strict=True)

    assert [video.url for video in out] == ["u1"]


def test_filter_by_query_falls_back_to_single_token_matches_when_needed() -> None:
    provider = PornhubProvider()
    videos = [
        Video(title="gay only title", url="u1"),
        Video(title="latino only title", url="u2"),
        Video(title="completely unrelated", url="u3"),
    ]

    out = provider._filter_by_query(videos, query="gay teen latino", progress=None, strict=False)

    assert [video.url for video in out] == ["u1", "u2"]


def test_search_url_uses_gay_path_when_orientation_is_gay() -> None:
    provider = PornhubProvider()
    base = provider._search_base_url(provider._effective_orientation("gay"))
    url = provider._search_url(base, "demo", 2)
    assert url == "https://www.pornhub.com/gay/video/search?search=demo&page=2"


def test_search_url_uses_lesbian_path_when_orientation_is_lesbian() -> None:
    provider = PornhubProvider()
    base = provider._search_base_url(provider._effective_orientation("lesbian"))
    url = provider._search_url(base, "demo", 2)
    assert url == "https://www.pornhub.com/lesbian/video/search?search=demo&page=2"


def test_search_url_uses_default_path_for_non_gay_orientation() -> None:
    provider = PornhubProvider()
    base = provider._search_base_url(provider._effective_orientation("bisexual"))
    url = provider._search_url(base, "demo", 1)
    assert url == "https://www.pornhub.com/video/search?search=demo&page=1"


def test_search_url_appends_filter_category_when_provided() -> None:
    provider = PornhubProvider()
    base = provider._search_base_url(provider._effective_orientation("any"))
    url = provider._search_url(base, "demo", 1, filter_category=35)
    assert url == "https://www.pornhub.com/video/search?search=demo&page=1&filter_category=35"


def test_effective_orientation_prefers_category_gay() -> None:
    provider = PornhubProvider()
    out = provider._effective_orientation("any", category="gay", query="random")
    assert out == "gay"


def test_effective_orientation_infers_gay_from_query_when_not_explicit() -> None:
    provider = PornhubProvider()
    out = provider._effective_orientation("any", category=None, query="best gay videos")
    assert out == "gay"


def test_normalized_search_query_removes_noise_chars() -> None:
    provider = PornhubProvider()
    query = provider._normalized_search_query("  élite + teen/latin 【mix】  ")
    assert query == "elite teen latin mix"


def test_video_from_webmaster_item_parses_duration_and_views() -> None:
    provider = PornhubProvider()
    item = {
        "title": "Example",
        "url": "https://www.pornhub.com/view_video.php?viewkey=ph123",
        "duration": "12:34",
        "views": "1,234",
    }

    video = provider._video_from_webmaster_item(item)
    assert video is not None
    assert video.duration_seconds == 754
    assert video.views == 1234


def test_extract_videos_from_page_html_collects_view_video_links() -> None:
    provider = PornhubProvider()
    html = """
    <html>
      <body>
        <ul id="videoSearchResult">
          <li class="videoblock">
            <a class="linkVideoThumb" href="/view_video.php?viewkey=phabc" title="Alpha Title"></a>
          </li>
        </ul>
        <a href="/view_video.php?viewkey=phdef">Beta Title</a>
      </body>
    </html>
    """
    videos = provider._extract_videos_from_page_html(html)
    assert [video.url for video in videos] == [
        "https://www.pornhub.com/view_video.php?viewkey=phabc",
        "https://www.pornhub.com/view_video.php?viewkey=phdef",
    ]
