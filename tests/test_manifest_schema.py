from __future__ import annotations

import unittest

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.manifest.schema import load_manifest_schema


class ManifestSchemaTests(unittest.TestCase):
    def test_schema_loads_with_expected_core_columns(self) -> None:
        schema = load_manifest_schema()
        self.assertIn("work_id", schema.fieldnames)
        self.assertIn("download_status", schema.fieldnames)
        self.assertIn("asr_status", schema.fieldnames)
        self.assertIn("txt_sync_status", schema.fieldnames)
        self.assertIn("dedup_status", schema.fieldnames)

    def test_default_row_contains_phase1_defaults(self) -> None:
        schema = load_manifest_schema()
        row = schema.make_default_row()
        self.assertEqual(row["platform"], "douyin")
        self.assertEqual(row["download_status"], "pending")
        self.assertEqual(row["asr_status"], "pending")
        self.assertEqual(row["txt_sync_status"], "pending")
        self.assertEqual(row["dedup_status"], "unknown")
        self.assertEqual(row["manual_reviewed"], "no")

    def test_download_ok_without_raw_video_path_warns(self) -> None:
        schema = load_manifest_schema()
        row = schema.make_default_row()
        row.update(
            {
                "work_id": "123",
                "author": "无名书生",
                "platform": "douyin",
                "video_link": "https://www.douyin.com/video/123",
                "title": "标题A",
                "download_status": "ok",
            }
        )
        issues = schema.validate_row(row, strict=False)
        self.assertTrue(any(issue.field == "raw_video_path" for issue in issues))

    def test_asr_ok_without_asr_text_path_warns(self) -> None:
        schema = load_manifest_schema()
        row = schema.make_default_row()
        row.update(
            {
                "work_id": "123",
                "author": "无名书生",
                "platform": "douyin",
                "video_link": "https://www.douyin.com/video/123",
                "title": "标题A",
                "download_status": "ok",
                "raw_video_path": "D:/raw/123.mp4",
                "asr_status": "ok",
            }
        )
        issues = schema.validate_row(row, strict=False)
        self.assertTrue(any(issue.field == "asr_text_path" for issue in issues))


if __name__ == "__main__":
    unittest.main()
