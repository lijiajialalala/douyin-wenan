from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.ingest.links import build_link_row, load_link_sources, merge_link_row


class IngestLinksTests(unittest.TestCase):
    def test_build_link_row_extracts_video_id_and_defaults(self) -> None:
        row = build_link_row(
            {
                "author": "无名书生",
                "video_link": "https://www.douyin.com/video/7633089780427091572",
                "title": "茶花女",
                "duration_text": "10:18",
                "likes": "14.2万",
            }
        )
        self.assertEqual(row["work_id"], "7633089780427091572")
        self.assertEqual(row["platform"], "douyin")
        self.assertEqual(row["download_status"], "pending")
        self.assertEqual(row["txt_sync_status"], "pending")
        self.assertEqual(row["duration_seconds"], "618")
        self.assertEqual(row["likes"], "142000")

    def test_merge_link_row_preserves_existing_operational_state(self) -> None:
        existing = {
            "work_id": "7633089780427091572",
            "author": "旧作者",
            "title": "旧标题",
            "video_link": "https://www.douyin.com/video/7633089780427091572",
            "download_status": "ok",
            "raw_video_path": "D:/raw/7633089780427091572.mp4",
            "notes": "older note",
        }
        incoming = {
            "author": "无名书生",
            "title": "新标题",
            "video_link": "https://www.douyin.com/video/7633089780427091572",
            "notes": "ingested from source links",
        }
        merged = merge_link_row(existing, incoming)
        self.assertEqual(merged["author"], "旧作者")
        self.assertEqual(merged["title"], "旧标题")
        self.assertEqual(merged["download_status"], "ok")
        self.assertEqual(merged["raw_video_path"], "D:/raw/7633089780427091572.mp4")
        self.assertIn("older note", merged["notes"])
        self.assertIn("ingested from source links", merged["notes"])

    def test_load_link_sources_requires_expected_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "links.csv"
            path.write_text("author,video_link,title\n无名书生,https://www.douyin.com/video/1,标题A\n", encoding="utf-8")
            rows = load_link_sources(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["author"], "无名书生")


if __name__ == "__main__":
    unittest.main()
