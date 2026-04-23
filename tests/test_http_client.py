from infrastructure.http_client import HttpClient


def test_parse_cookie_header_handles_browser_style_cookie_string() -> None:
    raw = (
        "rta_terms_accepted=1; cf_clearance=abc.def; "
        "g_state={\"i_l\":0,\"i_ll\":1776893111130}; mobileVersionWeb=classic"
    )
    out = HttpClient._parse_cookie_header(raw)
    assert ("rta_terms_accepted", "1") in out
    assert ("cf_clearance", "abc.def") in out
    assert ("mobileVersionWeb", "classic") in out
    assert ("g_state", "{\"i_l\":0,\"i_ll\":1776893111130}") in out


def test_parse_cookie_entries_handles_netscape_cookie_file() -> None:
    raw = (
        "# Netscape HTTP Cookie File\n"
        ".boyfriendtv.com\tTRUE\t/\tFALSE\t1786276589\tcf_clearance\tabc.def\n"
        "#HttpOnly_.boyfriendtv.com\tTRUE\t/\tFALSE\t1786276589\tmobileVersionWeb\tclassic\n"
    )
    out = HttpClient._parse_cookie_entries(raw)
    assert ("cf_clearance", "abc.def", ".boyfriendtv.com") in out
    assert ("mobileVersionWeb", "classic", ".boyfriendtv.com") in out


def test_cookie_string_applies_to_configured_domain() -> None:
    client = HttpClient(
        retries=0,
        backoff_seconds=0.0,
        request_cookie="cf_clearance=token123; mobileVersionWeb=classic",
        cookie_domain=".boyfriendtv.com",
    )
    names = {c.name for c in client.session.cookies}
    assert "cf_clearance" in names
    assert "mobileVersionWeb" in names
    domains = {c.domain for c in client.session.cookies if c.name == "cf_clearance"}
    assert ".boyfriendtv.com" in domains
