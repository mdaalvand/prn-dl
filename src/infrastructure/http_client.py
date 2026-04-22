from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import requests

from constants import DEFAULT_USER_AGENT


@dataclass
class HttpClient:
    retries: int
    backoff_seconds: float
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self._logger = logging.getLogger("phfetch.http")
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            }
        )
        self.session.cookies.set("platform", "pc")
        self.session.cookies.set("accessAgeDisclaimerPH", "1")
        self.session.cookies.set("accessPH", "1")
        self.session.cookies.set("age_verified", "1")

    def get_text(self, url: str, timeout: int, params: dict[str, object] | None = None) -> str:
        response = self._request("GET", url, timeout=timeout, params=params)
        return response.text

    def get_json(self, url: str, timeout: int, params: dict[str, object] | None = None) -> object:
        response = self._request("GET", url, timeout=timeout, params=params)
        return response.json()

    def _request(self, method: str, url: str, timeout: int, params: dict[str, object] | None = None) -> requests.Response:
        attempt = 0
        while True:
            try:
                response = self.session.request(method, url, params=params, timeout=timeout)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                if attempt >= self.retries:
                    raise
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
