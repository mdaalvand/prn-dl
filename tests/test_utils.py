from utils import parse_duration_to_seconds, parse_view_count


def test_parse_duration() -> None:
    assert parse_duration_to_seconds("02:30") == 150
    assert parse_duration_to_seconds("01:02:03") == 3723
    assert parse_duration_to_seconds("") is None


def test_parse_views() -> None:
    assert parse_view_count("1.2K") == 1200
    assert parse_view_count("3.4M") == 3_400_000
    assert parse_view_count("1200") == 1200
    assert parse_view_count("bad") is None
