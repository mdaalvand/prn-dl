from __future__ import annotations

import logging
import subprocess
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
    request_proxy: str = ""
    user_agent: str = DEFAULT_USER_AGENT

    def __post_init__(self) -> None:
        self._logger = logging.getLogger("phfetch.downloader")

    def download_batch(
        self,
        videos: list[Video],
        output_dir: str,
        quality: int,
        audio_only: bool,
        timeout: int,
    ) -> DownloadResult:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        succeeded: list[str] = []
        failed: list[str] = []
        failures: dict[str, str] = {}
        for video in videos:
            ok, reason = self._download_with_retry(video.url, output_dir, quality, audio_only, timeout)
            if ok:
                succeeded.append(video.url)
                continue
            failed.append(video.url)
            failures[video.url] = reason
        return DownloadResult(succeeded=succeeded, failed=failed, failures=failures)

    def _download_with_retry(self, url: str, output_dir: str, quality: int, audio_only: bool, timeout: int) -> tuple[bool, str]:
        last_reason = "unknown_error"
        for attempt in range(self.retries + 1):
            ok, reason = self._run_yt_dlp(url, output_dir, quality, audio_only, timeout)
            if ok:
                return True, ""
            last_reason = reason
            if attempt == self.retries:
                break
            sleep_seconds = self.backoff_seconds * (2**attempt)
            self._logger.warning("retry_download url=%s attempt=%s reason=%s", url, attempt + 1, reason)
            time.sleep(sleep_seconds)
        return False, last_reason

    def _run_yt_dlp(self, url: str, output_dir: str, quality: int, audio_only: bool, timeout: int) -> tuple[bool, str]:
        cmd = self._build_command(url, output_dir, quality, audio_only)
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

    def _build_command(self, url: str, output_dir: str, quality: int, audio_only: bool) -> list[str]:
        output_pattern = str(Path(output_dir) / "%(title)s.%(ext)s")
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
            "--impersonate",
            "chrome",
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
        if self.request_proxy:
            cmd.extend(["--proxy", self.request_proxy])
        if self.request_cookie:
            cmd.extend(["--add-header", f"Cookie: {self.request_cookie}"])
        return cmd
