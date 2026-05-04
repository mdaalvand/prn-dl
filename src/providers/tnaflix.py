from __future__ import annotations

import re
from urllib.parse import urlencode

from providers.search_base import SearchPageProvider


class TNAFlixProvider(SearchPageProvider):
    name = "tnaflix"
    source = "tnaflix"
    home_url = "https://www.tnaflix.com/"
    cookie_domain = ".tnaflix.com"
    result_link_pattern = re.compile(
        r'href="(?P<href>/(?:[^"]+/)?video\d+)"[^>]*',
        re.IGNORECASE,
    )

    def _search_url(self, query: str, page: int) -> str:
        params = {"search": query, "page": page}
        return f"https://www.tnaflix.com/search/?{urlencode(params)}"
