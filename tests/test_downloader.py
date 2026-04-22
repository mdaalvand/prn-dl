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


def test_build_options_include_numbered_output_prefix() -> None:
    downloader = YtDlpDownloader(retries=0, backoff_seconds=0.0)
    opts = downloader._build_ydl_opts(
        output_dir="downloads",
        quality=480,
        audio_only=False,
        process_timeout=300,
        number_prefix="007",
        impersonate_target="",
    )
    output_value = str(opts["outtmpl"])
    assert output_value.endswith("downloads/007 - %(title)s.%(ext)s")
