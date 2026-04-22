from __future__ import annotations

import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from yt_dlp import DownloadError, YoutubeDL

from constants import DEFAULT_USER_AGENT
from models import Video


@dataclass
class DownloadResult:
    succeeded: list[str]
    failed: list[str]
    failures: dict[str, str]


@dataclass
class YtDlpDownloader:
    retries: int
    backoff_seconds: float
    request_cookie: str = ""
    request_cookies_file: str = ""
    request_proxy: str = ""
    user_agent: str = DEFAULT_USER_AGENT
    impersonate_target: str = ""

    def __post_init__(self) -> None:
        self._logger = logging.getLogger("phfetch.downloader")
        self._temp_cookies_file = ""
        self._resolved_cookies_file = self._resolve_cookies_file()

    def _resolve_cookies_file(self) -> str:
        raw = (self.request_cookies_file or self.request_cookie or "").strip()
        if not raw:
            return ""
        if self._looks_like_cookie_file_content(raw):
            fd, temp_path = tempfile.mkstemp(prefix="phfetch-cookies-", suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(self._normalize_cookie_file_content(raw))
            self._temp_cookies_file = temp_path
            return temp_path
        maybe_path = Path(raw)
        if maybe_path.exists() and maybe_path.is_file():
            return str(maybe_path)
        return ""

    def _cleanup_temp_cookies_file(self) -> None:
        if not self._temp_cookies_file:
            return
        try:
            Path(self._temp_cookies_file).unlink(missing_ok=True)
        finally:
            self._temp_cookies_file = ""
            self._resolved_cookies_file = ""

    @staticmethod
    def _looks_like_cookie_file_content(value: str) -> bool:
        if "\n" not in value and "\t" not in value:
            return False
        if "# Netscape HTTP Cookie File" in value:
            return True
        lines = [line for line in value.splitlines() if line and not line.startswith("#")]
        return any(line.count("\t") >= 6 for line in lines)

    @staticmethod
    def _normalize_cookie_file_content(value: str) -> str:
        text = value.strip()
        if text.startswith("# Netscape HTTP Cookie File"):
            return text + "\n"
        return "# Netscape HTTP Cookie File\n" + text + "\n"

    def download_batch(
        self,
        videos: list[Video],
        output_dir: str,
        quality: int,
        audio_only: bool,
        timeout: int,
    ) -> DownloadResult:
        batch_started_at = time.perf_counter()
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            succeeded: list[str] = []
            failed: list[str] = []
            failures: dict[str, str] = {}
            for index, video in enumerate(videos, start=1):
                number_prefix = f"{index:03d}"
                item_started_at = time.perf_counter()
                self._logger.info(
                    "download_item_started index=%s total=%s url=%s quality=%s audio_only=%s",
                    index,
                    len(videos),
                    video.url,
                    quality,
                    audio_only,
                )
                ok, reason = self._download_with_retry(
                    video.url,
                    output_dir,
                    quality,
                    audio_only,
                    timeout,
                    number_prefix=number_prefix,
                )
                item_elapsed_ms = int((time.perf_counter() - item_started_at) * 1000)
                if ok:
                    succeeded.append(video.url)
                    self._logger.info(
                        "download_item_finished index=%s status=ok elapsed_ms=%s url=%s",
                        index,
                        item_elapsed_ms,
                        video.url,
                    )
                    continue
                failed.append(video.url)
                failures[video.url] = reason
                self._logger.warning(
                    "download_item_finished index=%s status=failed elapsed_ms=%s url=%s reason=%s",
                    index,
                    item_elapsed_ms,
                    video.url,
                    reason,
                )
            batch_elapsed_ms = int((time.perf_counter() - batch_started_at) * 1000)
            self._logger.info(
                "download_batch_finished total=%s succeeded=%s failed=%s elapsed_ms=%s",
                len(videos),
                len(succeeded),
                len(failed),
                batch_elapsed_ms,
            )
            return DownloadResult(succeeded=succeeded, failed=failed, failures=failures)
        finally:
            self._cleanup_temp_cookies_file()

    def _download_with_retry(
        self,
        url: str,
        output_dir: str,
        quality: int,
        audio_only: bool,
        timeout: int,
        number_prefix: str,
    ) -> tuple[bool, str]:
        last_reason = "unknown_error"
        for attempt in range(self.retries + 1):
            attempt_started_at = time.perf_counter()
            ok, reason = self._run_yt_dlp(
                url,
                output_dir,
                quality,
                audio_only,
                timeout,
                number_prefix=number_prefix,
            )
            attempt_elapsed_ms = int((time.perf_counter() - attempt_started_at) * 1000)
            self._logger.info(
                "download_attempt_finished url=%s attempt=%s/%s ok=%s elapsed_ms=%s",
                url,
                attempt + 1,
                self.retries + 1,
                ok,
                attempt_elapsed_ms,
            )
            if ok:
                return True, ""
            last_reason = reason
            if self._is_non_retriable_error(reason):
                break
            if attempt == self.retries:
                break
            sleep_seconds = self.backoff_seconds * (2**attempt)
            self._logger.warning("retry_download url=%s attempt=%s reason=%s", url, attempt + 1, reason)
            time.sleep(sleep_seconds)
        return False, last_reason

    def _run_yt_dlp(
        self,
        url: str,
        output_dir: str,
        quality: int,
        audio_only: bool,
        timeout: int,
        number_prefix: str,
    ) -> tuple[bool, str]:
        process_timeout = max(timeout * 12, 300)
        try:
            self._download_once(
                url=url,
                output_dir=output_dir,
                quality=quality,
                audio_only=audio_only,
                process_timeout=process_timeout,
                number_prefix=number_prefix,
                impersonate_target=self.impersonate_target,
            )
            return True, ""
        except DownloadError as exc:
            reason = str(exc) or "yt_dlp_non_zero_exit"
            if self._is_impersonate_not_available(reason) and self.impersonate_target:
                self._logger.warning(
                    "impersonate_unavailable_fallback url=%s target=%s",
                    url,
                    self.impersonate_target,
                )
                try:
                    self._download_once(
                        url=url,
                        output_dir=output_dir,
                        quality=quality,
                        audio_only=audio_only,
                        process_timeout=process_timeout,
                        number_prefix=number_prefix,
                        impersonate_target="",
                    )
                    return True, ""
                except DownloadError as fallback_exc:
                    reason = str(fallback_exc) or "yt_dlp_non_zero_exit_after_fallback"
            self._logger.error(
                "download_failed url=%s stderr=%s quality=%s output_dir=%s audio_only=%s",
                url,
                reason,
                quality,
                output_dir,
                audio_only,
            )
            return False, reason
        except Exception as exc:  # keep retry behavior for unexpected runtime errors
            reason = str(exc) or "yt_dlp_runtime_error"
            self._logger.error(
                "download_failed url=%s stderr=%s quality=%s output_dir=%s audio_only=%s",
                url,
                reason,
                quality,
                output_dir,
                audio_only,
            )
            return False, reason

    def _download_once(
        self,
        url: str,
        output_dir: str,
        quality: int,
        audio_only: bool,
        process_timeout: int,
        number_prefix: str,
        impersonate_target: str,
    ) -> None:
        opts = self._build_ydl_opts(
            output_dir=output_dir,
            quality=quality,
            audio_only=audio_only,
            process_timeout=process_timeout,
            number_prefix=number_prefix,
            impersonate_target=impersonate_target,
        )
        with YoutubeDL(opts) as ydl:
            ydl.download([url])

    def _build_ydl_opts(
        self,
        output_dir: str,
        quality: int,
        audio_only: bool,
        process_timeout: int,
        number_prefix: str,
        impersonate_target: str,
    ) -> dict[str, object]:
        output_pattern = str(Path(output_dir) / f"{number_prefix} - %(title)s.%(ext)s")
        if audio_only:
            format_selector = "bestaudio/best"
        else:
            format_selector = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"
        opts: dict[str, object] = {
            "format": format_selector,
            "outtmpl": output_pattern,
            "retries": 3,
            "extractor_retries": 3,
            "fragment_retries": 8,
            "socket_timeout": process_timeout,
            "http_headers": {
                "User-Agent": self.user_agent,
                "Referer": "https://www.pornhub.com/",
                "Origin": "https://www.pornhub.com",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "noprogress": True,
            "quiet": True,
            "no_warnings": False,
        }
        if impersonate_target:
            opts["impersonate"] = impersonate_target
        if self.request_proxy:
            opts["proxy"] = self.request_proxy
        if self._resolved_cookies_file:
            opts["cookiefile"] = self._resolved_cookies_file
        return opts

    def _is_impersonate_not_available(self, stderr: str) -> bool:
        low = stderr.lower()
        return "impersonate target" in low and "not available" in low

    def _is_non_retriable_error(self, reason: str) -> bool:
        low = reason.lower()
        return "flagged for verification in accordance with our trust and safety policy" in low
