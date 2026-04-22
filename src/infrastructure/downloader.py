from __future__ import annotations

import json
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
        batch_started_at = time.perf_counter()
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            succeeded: list[str] = []
            failed: list[str] = []
            failures: dict[str, str] = {}
            for index, video in enumerate(videos, start=1):
                number_prefix = f"{index:03d}"
                item_started_at = time.perf_counter()
                before_files = self._files_with_prefix(output_dir=output_dir, number_prefix=number_prefix)
                self._logger.info(
                    "download_item_started index=%s total=%s url=%s quality=%s audio_only=%s",
                    index,
                    len(videos),
                    video.url,
                    quality,
                    audio_only,
                )
                probe_started_at = time.perf_counter()
                probe = self._probe_video(url=video.url, quality=quality, audio_only=audio_only, timeout=timeout)
                probe_elapsed_ms = int((time.perf_counter() - probe_started_at) * 1000)
                self._logger.info(
                    "download_item_probe_finished index=%s elapsed_ms=%s estimated_size_mb=%s duration_s=%s requested_formats=%s",
                    index,
                    probe_elapsed_ms,
                    self._fmt_mb(probe.get("estimated_size_bytes")),
                    probe.get("duration_seconds"),
                    probe.get("requested_format_ids", ""),
                )
                download_started_at = time.perf_counter()
                ok, reason = self._download_with_retry(
                    video.url,
                    output_dir,
                    quality,
                    audio_only,
                    timeout,
                    number_prefix=number_prefix,
                )
                download_elapsed_ms = int((time.perf_counter() - download_started_at) * 1000)
                item_elapsed_ms = int((time.perf_counter() - item_started_at) * 1000)
                output_size_bytes = self._detect_output_size_bytes(
                    output_dir=output_dir,
                    number_prefix=number_prefix,
                    before_files=before_files,
                )
                avg_mbps = self._compute_avg_mbps(output_size_bytes=output_size_bytes, elapsed_ms=download_elapsed_ms)
                bottleneck_guess = self._guess_bottleneck(
                    probe_elapsed_ms=probe_elapsed_ms,
                    download_elapsed_ms=download_elapsed_ms,
                    avg_mbps=avg_mbps,
                    estimated_size_bytes=probe.get("estimated_size_bytes"),
                    has_separate_streams=probe.get("has_separate_streams", False),
                    failed=not ok,
                )
                if ok:
                    succeeded.append(video.url)
                    self._logger.info(
                        "download_item_finished index=%s status=ok elapsed_ms=%s url=%s",
                        index,
                        item_elapsed_ms,
                        video.url,
                    )
                    self._logger.info(
                        "download_item_profile index=%s probe_ms=%s download_ms=%s total_ms=%s output_size_mb=%s avg_mbps=%s bottleneck_guess=%s",
                        index,
                        probe_elapsed_ms,
                        download_elapsed_ms,
                        item_elapsed_ms,
                        self._fmt_mb(output_size_bytes),
                        self._fmt_float(avg_mbps),
                        bottleneck_guess,
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
                self._logger.warning(
                    "download_item_profile index=%s probe_ms=%s download_ms=%s total_ms=%s output_size_mb=%s avg_mbps=%s bottleneck_guess=%s",
                    index,
                    probe_elapsed_ms,
                    download_elapsed_ms,
                    item_elapsed_ms,
                    self._fmt_mb(output_size_bytes),
                    self._fmt_float(avg_mbps),
                    bottleneck_guess,
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
            ok, reason = self._run_yt_dlp(url, output_dir, quality, audio_only, timeout, number_prefix=number_prefix)
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

    def _probe_video(self, url: str, quality: int, audio_only: bool, timeout: int) -> dict[str, object]:
        cmd = self._build_probe_command(url=url, quality=quality, audio_only=audio_only)
        process_timeout = max(timeout * 4, 120)
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=process_timeout)
        except subprocess.TimeoutExpired:
            return {}
        if completed.returncode != 0:
            return {}
        payload = self._parse_probe_payload(completed.stdout)
        if not payload:
            return {}
        return self._extract_probe_info(payload)

    def _build_probe_command(self, url: str, quality: int, audio_only: bool) -> list[str]:
        if audio_only:
            format_selector = "bestaudio/best"
        else:
            format_selector = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--dump-single-json",
            "--no-warnings",
            "-f",
            format_selector,
            url,
        ]
        if self.impersonate_target:
            cmd.extend(["--impersonate", self.impersonate_target])
        if self.request_proxy:
            cmd.extend(["--proxy", self.request_proxy])
        if self._resolved_cookies_file:
            cmd.extend(["--cookies", self._resolved_cookies_file])
        elif self.request_cookie:
            cmd.extend(["--add-header", f"Cookie: {self.request_cookie}"])
        return cmd

    def _parse_probe_payload(self, stdout: str) -> dict[str, object]:
        text = stdout.strip()
        if not text:
            return {}
        for line in reversed(text.splitlines()):
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return {}

    def _extract_probe_info(self, payload: dict[str, object]) -> dict[str, object]:
        requested_formats = payload.get("requested_formats")
        format_ids: list[str] = []
        estimated_size_bytes = 0
        has_separate_streams = False
        if isinstance(requested_formats, list):
            has_separate_streams = len(requested_formats) > 1
            for entry in requested_formats:
                if not isinstance(entry, dict):
                    continue
                format_id = str(entry.get("format_id") or "").strip()
                if format_id:
                    format_ids.append(format_id)
                size_value = entry.get("filesize") or entry.get("filesize_approx") or 0
                if isinstance(size_value, (int, float)):
                    estimated_size_bytes += int(size_value)
        if estimated_size_bytes <= 0:
            size_value = payload.get("filesize") or payload.get("filesize_approx") or 0
            if isinstance(size_value, (int, float)):
                estimated_size_bytes = int(size_value)
        duration_value = payload.get("duration")
        duration_seconds = int(duration_value) if isinstance(duration_value, (int, float)) else None
        return {
            "estimated_size_bytes": estimated_size_bytes if estimated_size_bytes > 0 else None,
            "duration_seconds": duration_seconds,
            "requested_format_ids": ",".join(format_ids),
            "has_separate_streams": has_separate_streams,
        }

    def _files_with_prefix(self, output_dir: str, number_prefix: str) -> set[Path]:
        directory = Path(output_dir)
        if not directory.exists():
            return set()
        return {path for path in directory.glob(f"{number_prefix} - *") if path.is_file()}

    def _detect_output_size_bytes(self, output_dir: str, number_prefix: str, before_files: set[Path]) -> int | None:
        after_files = self._files_with_prefix(output_dir=output_dir, number_prefix=number_prefix)
        new_files = [path for path in after_files if path not in before_files]
        if new_files:
            candidate = max(new_files, key=lambda path: path.stat().st_mtime)
            return candidate.stat().st_size
        if after_files:
            candidate = max(after_files, key=lambda path: path.stat().st_mtime)
            return candidate.stat().st_size
        return None

    def _compute_avg_mbps(self, output_size_bytes: int | None, elapsed_ms: int) -> float | None:
        if output_size_bytes is None or output_size_bytes <= 0 or elapsed_ms <= 0:
            return None
        bits = float(output_size_bytes) * 8.0
        seconds = float(elapsed_ms) / 1000.0
        return bits / seconds / 1_000_000.0

    def _guess_bottleneck(
        self,
        probe_elapsed_ms: int,
        download_elapsed_ms: int,
        avg_mbps: float | None,
        estimated_size_bytes: int | None,
        has_separate_streams: bool,
        failed: bool,
    ) -> str:
        if failed:
            return "download_or_provider_error"
        if probe_elapsed_ms > max(4000, int(download_elapsed_ms * 0.25)):
            return "metadata_extract_slow"
        if avg_mbps is not None:
            if avg_mbps < 1.0:
                return "network_very_slow"
            if avg_mbps < 3.0:
                return "network_slow"
            if avg_mbps < 8.0:
                return "network_moderate"
        if has_separate_streams and download_elapsed_ms > 90000:
            return "large_transfer_or_merge_overhead"
        if estimated_size_bytes and estimated_size_bytes > 500 * 1024 * 1024:
            return "large_file_transfer"
        return "normal_transfer"

    def _fmt_mb(self, size_bytes: int | None) -> str:
        if size_bytes is None:
            return "n/a"
        return f"{size_bytes / (1024 * 1024):.2f}"

    def _fmt_float(self, value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:.2f}"

    def _is_impersonate_not_available(self, stderr: str) -> bool:
        low = stderr.lower()
        return "impersonate target" in low and "not available" in low

    def _is_non_retriable_error(self, reason: str) -> bool:
        low = reason.lower()
        return "flagged for verification in accordance with our trust and safety policy" in low
