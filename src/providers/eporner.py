from __future__ import annotations

import re
from urllib.parse import urlencode

from providers.search_base import SearchPageProvider


class EpornerProvider(SearchPageProvider):
    name = "eporner"
    source = "eporner"
    home_url = "https://www.eporner.com/"
    cookie_domain = ".eporner.com"
    result_link_pattern = re.compile(
        r'href="(?P<href>/(?:hd-porn|video-)[^"]+)"[^>]*',
        re.IGNORECASE,
    )

    def _search_url(self, query: str, page: int) -> str:
        params = {"search": query, "page": page}
        return f"https://www.eporner.com/search/?{urlencode(params)}"
