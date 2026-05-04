from providers.tnaflix import TNAFlixProvider


def test_search_url_uses_query_and_page() -> None:
    provider = TNAFlixProvider()
    url = provider._search_url(query="alpha beta", page=2)
    assert url == "https://www.tnaflix.com/search/?search=alpha+beta&page=2"


def test_extract_videos_from_page_html_collects_video_links() -> None:
    provider = TNAFlixProvider()
    html = """
    <html>
      <body>
        <a href="/teen-porn/sample-title/video123" title="Sample One"></a>
        <a href="/amateur-porn/another-title/video456" title="Sample Two"></a>
      </body>
    </html>
    """
    videos = provider._extract_videos_from_page_html(html)
    assert [video.url for video in videos] == [
        "https://www.tnaflix.com/teen-porn/sample-title/video123",
        "https://www.tnaflix.com/amateur-porn/another-title/video456",
    ]
    assert [video.source for video in videos] == ["tnaflix", "tnaflix"]
