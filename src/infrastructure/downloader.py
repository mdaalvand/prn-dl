from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

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
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            succeeded: list[str] = []
            failed: list[str] = []
            failures: dict[str, str] = {}
            for index, video in enumerate(videos, start=1):
                number_prefix = f"{index:03d}"
                ok, reason = self._download_with_retry(
                    video.url,
                    output_dir,
                    quality,
                    audio_only,
                    timeout,
                    number_prefix=number_prefix,
                )
                if ok:
                    succeeded.append(video.url)
                    continue
                failed.append(video.url)
                failures[video.url] = reason
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
            ok, reason = self._run_yt_dlp(url, output_dir, quality, audio_only, timeout, number_prefix=number_prefix)
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
        cmd = self._build_command(
            url,
            output_dir,
            quality,
            audio_only,
            impersonate_target=self.impersonate_target,
            number_prefix=number_prefix,
        )
        process_timeout = max(timeout * 12, 300)
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=process_timeout)
        except subprocess.TimeoutExpired:
            reason = f"timeout_after_{process_timeout}s"
            self._logger.error(
                "download_failed url=%s reason=%s quality=%s output_dir=%s audio_only=%s",
                url,
                reason,
                quality,
                output_dir,
                audio_only,
            )
            return False, reason
        if completed.returncode == 0:
            return True, ""
        stderr = completed.stderr.strip() or "yt_dlp_non_zero_exit"
        if self._is_impersonate_not_available(stderr) and self.impersonate_target:
            fallback_cmd = self._build_command(
                url,
                output_dir,
                quality,
                audio_only,
                impersonate_target="",
                number_prefix=number_prefix,
            )
            self._logger.warning(
                "impersonate_unavailable_fallback url=%s target=%s",
                url,
                self.impersonate_target,
            )
            try:
                completed = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=process_timeout)
            except subprocess.TimeoutExpired:
                return False, f"timeout_after_{process_timeout}s"
            if completed.returncode == 0:
                return True, ""
            stderr = completed.stderr.strip() or "yt_dlp_non_zero_exit_after_fallback"
        self._logger.error(
            "download_failed url=%s code=%s stderr=%s quality=%s output_dir=%s audio_only=%s",
            url,
            completed.returncode,
            stderr,
            quality,
            output_dir,
            audio_only,
        )
        return False, stderr

    def _build_command(
        self,
        url: str,
        output_dir: str,
        quality: int,
        audio_only: bool,
        impersonate_target: str,
        number_prefix: str,
    ) -> list[str]:
        output_pattern = str(Path(output_dir) / f"{number_prefix} - %(title)s.%(ext)s")
        if audio_only:
            format_selector = "bestaudio/best"
        else:
            format_selector = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"
        cmd = [
            "yt-dlp",
            "--no-progress",
            "--retries",
            "3",
            "--extractor-retries",
            "3",
            "--fragment-retries",
            "8",
            "--user-agent",
            self.user_agent,
            "--referer",
            "https://www.pornhub.com/",
            "--add-header",
            "Origin: https://www.pornhub.com",
            "--add-header",
            "Accept-Language: en-US,en;q=0.9",
            "-f",
            format_selector,
            "-o",
            output_pattern,
            url,
        ]
        if impersonate_target:
            cmd.extend(["--impersonate", impersonate_target])
        if self.request_proxy:
            cmd.extend(["--proxy", self.request_proxy])
        if self._resolved_cookies_file:
            cmd.extend(["--cookies", self._resolved_cookies_file])
        elif self.request_cookie:
            cmd.extend(["--add-header", f"Cookie: {self.request_cookie}"])
        return cmd

    def _is_impersonate_not_available(self, stderr: str) -> bool:
        low = stderr.lower()
        return "impersonate target" in low and "not available" in low

    def _is_non_retriable_error(self, reason: str) -> bool:
        low = reason.lower()
        return "flagged for verification in accordance with our trust and safety policy" in low
