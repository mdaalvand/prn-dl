from providers.boyfriendtv import BoyfriendtvProvider


def test_search_url_uses_query_and_page() -> None:
    provider = BoyfriendtvProvider()
    url = provider._search_url(query="alpha beta", page=2)
    assert url == "https://www.boyfriendtv.com/search?query=alpha+beta&page=2"


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
