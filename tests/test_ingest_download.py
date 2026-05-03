from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.ingest.download import (
    build_candidate_media_urls,
    build_output_path,
    extract_play_addr_url,
    resolve_media_url,
    resolve_media_urls,
)
from douyin_wenan.manifest.transitions import mark_download_failed, mark_download_succeeded


class IngestDownloadTests(unittest.TestCase):
    def test_extract_play_addr_url_decodes_escaped_url(self) -> None:
        html = (
            '<script>"play_addr":{"uri":"abc","url_list":['
            '"https:\\u002F\\u002Faweme.snssdk.com\\u002Faweme\\u002Fv1\\u002Fplaywm\\u002F?video_id=abc"]}</script>'
        )
        url = extract_play_addr_url(html)
        self.assertEqual(url, "https://aweme.snssdk.com/aweme/v1/playwm/?video_id=abc")

    def test_build_output_path_is_author_scoped_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = build_output_path(raw_video_dir=Path(tmpdir), author="无名书生", work_id="123")
        self.assertTrue(str(path).endswith("无名书生\\123.mp4"))

    def test_resolve_media_url_uses_share_page_html(self) -> None:
        session = MagicMock()
        response = MagicMock()
        response.text = (
            '<html>"play_addr":{"uri":"abc","url_list":['
            '"https:\\u002F\\u002Faweme.snssdk.com\\u002Faweme\\u002Fv1\\u002Fplaywm\\u002F?video_id=abc"]}</html>'
        )
        response.raise_for_status.return_value = None
        session.get.return_value = response
        url = resolve_media_url(session, "https://www.iesdouyin.com/share/video/123/")
        self.assertEqual(url, "https://aweme.snssdk.com/aweme/v1/playwm/?video_id=abc")

    def test_resolve_media_urls_prefers_play_before_playwm(self) -> None:
        session = MagicMock()
        response = MagicMock()
        response.text = (
            '<html>"play_addr":{"uri":"abc","url_list":['
            '"https:\\u002F\\u002Faweme.snssdk.com\\u002Faweme\\u002Fv1\\u002Fplaywm\\u002F?video_id=abc"]}</html>'
        )
        response.raise_for_status.return_value = None
        session.get.return_value = response
        urls = resolve_media_urls(session, "https://www.iesdouyin.com/share/video/123/")
        self.assertEqual(
            urls,
            [
                "https://aweme.snssdk.com/aweme/v1/play/?video_id=abc",
                "https://aweme.snssdk.com/aweme/v1/playwm/?video_id=abc",
            ],
        )

    def test_build_candidate_media_urls_deduplicates(self) -> None:
        self.assertEqual(
            build_candidate_media_urls("https://example.com/video.mp4"),
            ["https://example.com/video.mp4"],
        )

    def test_mark_download_succeeded_sets_state_and_path(self) -> None:
        row = {"download_status": "pending", "raw_video_path": "", "download_time": "", "notes": ""}
        mark_download_succeeded(row, raw_video_path="D:/raw/123.mp4", note="downloaded 10 bytes")
        self.assertEqual(row["download_status"], "ok")
        self.assertEqual(row["raw_video_path"], "D:/raw/123.mp4")
        self.assertTrue(row["download_time"])
        self.assertIn("downloaded 10 bytes", row["notes"])

    def test_mark_download_failed_sets_failed_state_and_reason(self) -> None:
        row = {"download_status": "pending", "raw_video_path": "x.mp4", "notes": ""}
        mark_download_failed(row, reason="timeout")
        self.assertEqual(row["download_status"], "failed")
        self.assertEqual(row["raw_video_path"], "")
        self.assertIn("timeout", row["notes"])


if __name__ == "__main__":
    unittest.main()
