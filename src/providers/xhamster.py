from __future__ import annotations

import re
from urllib.parse import urlencode

from providers.search_base import SearchPageProvider


class XHamsterProvider(SearchPageProvider):
    name = "xhamster"
    source = "xhamster"
    home_url = "https://xhamster.com/"
    cookie_domain = ".xhamster.com"
    result_link_pattern = re.compile(
        r'href="(?P<href>/(?:videos/[^"]+|movies/\d+/[^"]+\.html))"[^>]*',
        re.IGNORECASE,
    )

    def _search_url(self, query: str, page: int) -> str:
        params = {"search": query, "page": page}
        return f"https://xhamster.com/search/?{urlencode(params)}"
