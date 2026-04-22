from filters import apply_filters, normalize_orientation, sort_videos
from models import Video


def sample_data() -> list[Video]:
    return [
        Video(title="alpha hd", url="u1", duration_seconds=120, views=2000, is_hd=True),
        Video(title="beta", url="u2", duration_seconds=360, views=9000, is_hd=False),
        Video(title="gamma hd", url="u3", duration_seconds=60, views=1500, is_hd=True),
    ]


def test_apply_filters() -> None:
    items = sample_data()
    out = apply_filters(items, min_duration=100, min_views=1800, hd_only=True)
    assert len(out) == 1
    assert out[0].title == "alpha hd"


def test_sort_views_desc() -> None:
    items = sample_data()
    out = sort_videos(items, by="views")
    assert [item.url for item in out] == ["u2", "u1", "u3"]


def test_sort_duration_desc() -> None:
    items = sample_data()
    out = sort_videos(items, by="duration")
    assert [item.url for item in out] == ["u2", "u1", "u3"]


def test_orientation_no_longer_drops_results_by_title_keywords() -> None:
    items = [
        Video(title="hot gay scene", url="u1"),
        Video(title="straight couple", url="u2"),
    ]
    out = apply_filters(items, orientation="gay")
    assert [item.url for item in out] == ["u1", "u2"]


def test_orientation_alias_farsi_is_accepted_without_local_title_filtering() -> None:
    items = [
        Video(title="bisexual threesome", url="u1"),
        Video(title="straight couple", url="u2"),
    ]
    out = apply_filters(items, orientation="دوجنسه")
    assert [item.url for item in out] == ["u1", "u2"]


def test_normalize_orientation_unknown_value() -> None:
    assert normalize_orientation("unknown") is None
