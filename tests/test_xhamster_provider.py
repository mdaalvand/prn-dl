from providers.xhamster import XHamsterProvider


def test_search_url_uses_query_and_page() -> None:
    provider = XHamsterProvider()
    url = provider._search_url(query="alpha beta", page=2)
    assert url == "https://xhamster.com/search/?search=alpha+beta&page=2"


def test_extract_videos_from_page_html_collects_video_links() -> None:
    provider = XHamsterProvider()
    html = """
    <html>
      <body>
        <a href="/videos/sample-video-1" title="Sample One"></a>
        <a href="/movies/12345/another-video.html" title="Sample Two"></a>
      </body>
    </html>
    """
    videos = provider._extract_videos_from_page_html(html)
    assert [video.url for video in videos] == [
        "https://xhamster.com/videos/sample-video-1",
        "https://xhamster.com/movies/12345/another-video.html",
    ]
    assert [video.source for video in videos] == ["xhamster", "xhamster"]
