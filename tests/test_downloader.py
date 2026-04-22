from pathlib import Path

from infrastructure.downloader import YtDlpDownloader


def test_raw_cookie_file_content_is_materialized_and_cleaned() -> None:
    raw = "# Netscape HTTP Cookie File\n.pornhub.com\tTRUE\t/\tFALSE\t1786276589\tfoo\tbar\n"
    downloader = YtDlpDownloader(retries=0, backoff_seconds=0.0, request_cookies_file=raw)
    temp_path = downloader._resolved_cookies_file

    assert temp_path
    assert temp_path != raw
    assert downloader._temp_cookies_file == temp_path
    assert Path(temp_path).exists()

    downloader.download_batch(videos=[], output_dir="downloads", quality=720, audio_only=False, timeout=30)

    assert downloader._temp_cookies_file == ""
    assert not Path(temp_path).exists()


def test_build_command_includes_numbered_output_prefix() -> None:
    downloader = YtDlpDownloader(retries=0, backoff_seconds=0.0)
    cmd = downloader._build_command(
        url="https://www.pornhub.com/view_video.php?viewkey=abc",
        output_dir="downloads",
        quality=480,
        audio_only=False,
        impersonate_target="",
        number_prefix="007",
    )
    output_value = cmd[cmd.index("-o") + 1]
    assert output_value.endswith("downloads/007 - %(title)s.%(ext)s")
