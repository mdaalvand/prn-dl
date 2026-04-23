from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import requests

from constants import DEFAULT_USER_AGENT
from errors import HttpRequestError


@dataclass
class HttpClient:
    retries: int
    backoff_seconds: float
    request_cookie: str = ""
    request_proxy: str = ""
    cookie_domain: str = ".pornhub.com"
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self._logger = logging.getLogger("phfetch.http")
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Linux"',
                "Referer": "https://www.pornhub.com/",
                "Origin": "https://www.pornhub.com",
            }
        )
        self.session.cookies.set("platform", "pc")
        self.session.cookies.set("accessAgeDisclaimerPH", "1")
        self.session.cookies.set("accessPH", "1")
        self.session.cookies.set("age_verified", "1")
        self._set_cookie_string(self.request_cookie)
        self._set_proxy(self.request_proxy)

    def warmup(self, timeout: int, url: str = "https://www.pornhub.com/") -> None:
        try:
            self.session.get(url, timeout=timeout)
        except requests.RequestException:
            return

    def _set_proxy(self, proxy: str) -> None:
        if not proxy:
            return
        self.session.proxies.update({"http": proxy, "https": proxy})

    def _set_cookie_string(self, cookie_string: str) -> None:
        if not cookie_string:
            return
        for key, value, domain in self._parse_cookie_entries(cookie_string):
            cookie_kwargs = {"domain": domain} if domain else {}
            if not cookie_kwargs and self.cookie_domain:
                cookie_kwargs["domain"] = self.cookie_domain
            self.session.cookies.set(key, value, **cookie_kwargs)

    @staticmethod
    def _parse_cookie_entries(cookie_header: str) -> list[tuple[str, str, str | None]]:
        entries: list[tuple[str, str, str | None]] = []
        entries.extend(HttpClient._parse_netscape_cookie_file(cookie_header))
        if entries:
            return entries
        entries.extend((key, value, None) for key, value in HttpClient._parse_cookie_header(cookie_header))
        return entries

    @staticmethod
    def _parse_cookie_header(cookie_header: str) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for chunk in cookie_header.split(";"):
            part = chunk.strip()
            if not part or "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            pairs.append((key, value))
        return pairs

    @staticmethod
    def _parse_netscape_cookie_file(cookie_string: str) -> list[tuple[str, str, str | None]]:
        entries: list[tuple[str, str, str | None]] = []
        for raw_line in cookie_string.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#") and not line.startswith("#HttpOnly_"):
                continue
            parts = raw_line.split("\t")
            if len(parts) < 7:
                continue
            domain = parts[0].strip()
            if domain.startswith("#HttpOnly_"):
                domain = domain.removeprefix("#HttpOnly_")
            name = parts[5].strip()
            value = "\t".join(parts[6:]).strip()
            if not name:
                continue
            entries.append((name, value, domain or None))
        return entries

    def get_text(self, url: str, timeout: int, params: dict[str, object] | None = None) -> str:
        response = self._request("GET", url, timeout=timeout, params=params)
        return response.text

    def get_json(self, url: str, timeout: int, params: dict[str, object] | None = None) -> object:
        response = self._request("GET", url, timeout=timeout, params=params)
        return response.json()

    def _request(self, method: str, url: str, timeout: int, params: dict[str, object] | None = None) -> requests.Response:
        attempt = 0
        last_exc: requests.RequestException | None = None
        while True:
            try:
                response = self.session.request(method, url, params=params, timeout=timeout)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.retries:
                    status_code = None
                    reason = str(exc)
                    if isinstance(exc, requests.HTTPError) and exc.response is not None:
                        status_code = exc.response.status_code
                        reason = f"{exc.response.status_code} {exc.response.reason}"
                    raise HttpRequestError(
                        method=method,
                        url=url,
                        attempts=attempt + 1,
                        status_code=status_code,
                        reason=reason,
                    ) from last_exc
                sleep_seconds = self.backoff_seconds * (2**attempt)
                self._logger.warning(
                    "request_failed method=%s url=%s attempt=%s err=%s",
                    method,
                    url,
                    attempt + 1,
                    exc,
                )
                time.sleep(sleep_seconds)
                attempt += 1
