from providers.eporner import EpornerProvider


def test_search_url_uses_query_and_page() -> None:
    provider = EpornerProvider()
    url = provider._search_url(query="alpha beta", page=2)
    assert url == "https://www.eporner.com/search/?search=alpha+beta&page=2"


def test_extract_videos_from_page_html_collects_video_links() -> None:
    provider = EpornerProvider()
    html = """
    <html>
      <body>
        <a href="/hd-porn/abc123/sample-video/" title="Sample One"></a>
        <a href="/video-xyz789/another-video/" title="Sample Two"></a>
      </body>
    </html>
    """
    videos = provider._extract_videos_from_page_html(html)
    assert [video.url for video in videos] == [
        "https://www.eporner.com/hd-porn/abc123/sample-video/",
        "https://www.eporner.com/video-xyz789/another-video/",
    ]
    assert [video.source for video in videos] == ["eporner", "eporner"]
