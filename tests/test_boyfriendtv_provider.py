from providers.boyfriendtv import BoyfriendtvProvider


def test_search_url_uses_query_and_page() -> None:
    provider = BoyfriendtvProvider()
    url = provider._search_url(query="alpha beta", page=2)
    assert url == "https://www.boyfriendtv.com/search/?q=alpha+beta&page=2"


def test_extract_videos_from_page_html_collects_video_links() -> None:
    provider = BoyfriendtvProvider()
    html = """
    <html>
      <body>
        <a href="/videos/sample-video-1" title="Sample One"></a>
        <a href="/video/sample-video-2" title="Sample Two"></a>
      </body>
    </html>
    """
    videos = provider._extract_videos_from_page_html(html)
    assert [video.url for video in videos] == [
        "https://www.boyfriendtv.com/videos/sample-video-1",
        "https://www.boyfriendtv.com/video/sample-video-2",
    ]
    assert [video.source for video in videos] == ["boyfriendtv", "boyfriendtv"]


def test_search_videos_sets_boyfriendtv_headers_and_warmup_url() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.headers = {}

        def update(self, values):
            self.headers.update(values)

    class FakeHttpClient:
        def __init__(self) -> None:
            self.session = FakeSession()
            self.warmup_calls = []

        def warmup(self, timeout: int, url: str = "https://www.pornhub.com/") -> None:
            self.warmup_calls.append((timeout, url))

        def get_text(self, url: str, timeout: int) -> str:
            _ = (url, timeout)
            return ""

    fake_http = FakeHttpClient()
    provider = BoyfriendtvProvider(http_client=fake_http)
    provider.search_videos(query="demo", timeout=7, max_pages=1)

    assert fake_http.session.headers["Referer"] == "https://www.boyfriendtv.com/"
    assert fake_http.session.headers["Origin"] == "https://www.boyfriendtv.com"
    assert fake_http.warmup_calls == [(7, "https://www.boyfriendtv.com/")]
