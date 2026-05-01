from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema


class ManifestRepositoryTests(unittest.TestCase):
    def test_init_empty_creates_header_only_manifest(self) -> None:
        schema = load_manifest_schema()
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "douyin_manifest.csv"
            repo = ManifestRepository(manifest_path, schema)

            repo.init_empty()

            self.assertTrue(manifest_path.exists())
            rows = repo.load_rows()
            self.assertEqual(rows, [])

    def test_upsert_row_inserts_and_updates_by_work_id(self) -> None:
        schema = load_manifest_schema()
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "douyin_manifest.csv"
            repo = ManifestRepository(manifest_path, schema)
            repo.init_empty()

            row = schema.make_default_row()
            row.update(
                {
                    "work_id": "7633089780427091572",
                    "author": "无名书生",
                    "platform": "douyin",
                    "video_link": "https://www.douyin.com/video/7633089780427091572",
                    "title": "茶花女",
                }
            )
            repo.upsert_row(row)

            updated = dict(row)
            updated["title"] = "茶花女（更新）"
            repo.upsert_row(updated)

            rows = repo.load_rows()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "茶花女（更新）")


if __name__ == "__main__":
    unittest.main()
