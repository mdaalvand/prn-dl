from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from models import Video


@dataclass
class DownloadResult:
    succeeded: list[str]
    failed: list[str]


@dataclass
class YtDlpDownloader:
    retries: int
    backoff_seconds: float

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
        for video in videos:
            if self._download_with_retry(video.url, output_dir, quality, audio_only, timeout):
                succeeded.append(video.url)
                continue
            failed.append(video.url)
        return DownloadResult(succeeded=succeeded, failed=failed)

    def _download_with_retry(self, url: str, output_dir: str, quality: int, audio_only: bool, timeout: int) -> bool:
        for attempt in range(self.retries + 1):
            if self._run_yt_dlp(url, output_dir, quality, audio_only, timeout):
                return True
            if attempt == self.retries:
                break
            sleep_seconds = self.backoff_seconds * (2**attempt)
            self._logger.warning("retry_download url=%s attempt=%s", url, attempt + 1)
            time.sleep(sleep_seconds)
        return False

    def _run_yt_dlp(self, url: str, output_dir: str, quality: int, audio_only: bool, timeout: int) -> bool:
        cmd = self._build_command(url, output_dir, quality, audio_only)
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout * 6)
        if completed.returncode == 0:
            return True
        self._logger.error(
            "download_failed url=%s code=%s stderr=%s",
            url,
            completed.returncode,
            completed.stderr.strip(),
        )
        return False

    def _build_command(self, url: str, output_dir: str, quality: int, audio_only: bool) -> list[str]:
        output_pattern = str(Path(output_dir) / "%(title)s.%(ext)s")
        if audio_only:
            format_selector = "bestaudio/best"
        else:
            format_selector = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"
        return [
            "yt-dlp",
            "--no-progress",
            "--retries",
            "3",
            "-f",
            format_selector,
            "-o",
            output_pattern,
            url,
        ]
