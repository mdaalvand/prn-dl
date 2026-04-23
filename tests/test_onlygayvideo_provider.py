from providers.onlygayvideo import OnlyGayVideoProvider


def test_search_url_uses_query_and_page() -> None:
    provider = OnlyGayVideoProvider()
    url = provider._search_url(query="alpha beta", page=2)
    assert url == "https://www.onlygayvideo.com/search/?q=alpha+beta&page=2"


def test_extract_videos_from_page_html_collects_video_metadata() -> None:
    provider = OnlyGayVideoProvider()
    html = """
    <div class="item">
      <a href="https://www.onlygayvideo.com/videos/123/demo/" title="Demo Title">
        <div class="img"><span class="is-hd">HD</span></div>
        <strong class="title">Demo Title</strong>
        <div class="wrap">
          <div class="duration">12:34</div>
          <div class="rating positive">88%</div>
        </div>
        <div class="wrap">
          <div class="added"><em>8 years ago</em></div>
          <div class="views">42K</div>
        </div>
      </a>
    </div>
    """
    videos = provider._extract_videos_from_page_html(html)
    assert len(videos) == 1
    video = videos[0]
    assert video.title == "Demo Title"
    assert video.url == "https://www.onlygayvideo.com/videos/123/demo/"
    assert video.duration_seconds == 754
    assert video.views == 42000
    assert video.is_hd is True
    assert video.source == "onlygayvideo"
