from __future__ import annotations


class AppError(Exception):
    """Base application error."""


class HttpRequestError(AppError):
    def __init__(
        self,
        *,
        method: str,
        url: str,
        attempts: int,
        status_code: int | None,
        reason: str,
    ) -> None:
        super().__init__(reason)
        self.method = method
        self.url = url
        self.attempts = attempts
        self.status_code = status_code
        self.reason = reason

