from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema


REPO_ROOT = Path(__file__).resolve().parents[1]


def _base_row(*, work_id: str, author: str = "无名书生") -> dict[str, str]:
    schema = load_manifest_schema()
    row = schema.make_default_row()
    row.update(
        {
            "work_id": work_id,
            "author": author,
            "platform": "douyin",
            "video_link": f"https://www.douyin.com/video/{work_id}",
            "title": "标题A",
            "download_status": "ok",
            "raw_video_path": f"D:/runtime/assets/raw_videos/{author}/{work_id}.mp4",
            "asr_status": "ok",
        }
    )
    return row


def _run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, f"scripts/{script_name}", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class RefreshBatchTests(unittest.TestCase):
    def test_reclean_existing_failure_keeps_ok_state_and_records_note(self) -> None:
        schema = load_manifest_schema()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = tmp / "douyin_manifest.csv"
            repo = ManifestRepository(manifest_path, schema)
            repo.init_empty()

            row = _base_row(work_id="7633089780427091572")
            row.update(
                {
                    "asr_text_path": str((tmp / "missing-asr.txt").resolve()),
                    "asr_provider": "legacy-provider",
                    "asr_model": "legacy-model",
                    "asr_time": "2026-05-01T00:00:00+08:00",
                    "txt_sync_status": "ok",
                    "txt_path": str((tmp / "runtime.txt").resolve()),
                    "dedup_status": "unique",
                }
            )
            repo.upsert_row(row)

            result = _run_script(
                "run_asr_batch.py",
                "--manifest-path",
                str(manifest_path),
                "--reclean-existing",
                "--author",
                "无名书生",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            updated = repo.index_by("work_id")["7633089780427091572"]
            self.assertEqual(updated["asr_status"], "ok")
            self.assertEqual(updated["txt_sync_status"], "ok")
            self.assertEqual(updated["txt_path"], str((tmp / "runtime.txt").resolve()))
            self.assertEqual(updated["asr_provider"], "legacy-provider")
            self.assertEqual(updated["asr_model"], "legacy-model")
            self.assertEqual(updated["asr_time"], "2026-05-01T00:00:00+08:00")
            self.assertIn("asr reclean failed:", updated["notes"])

    def test_reclean_existing_preserves_asr_provenance(self) -> None:
        schema = load_manifest_schema()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = tmp / "douyin_manifest.csv"
            repo = ManifestRepository(manifest_path, schema)
            repo.init_empty()

            asr_text_path = tmp / "asr.txt"
            asr_text_path.write_text(
                "🎼阿尔蒙被老鸭毛反咬后当场科血。这是一段足够长的正文内容，用来触发尾部平台标记清理。抖音。",
                encoding="utf-8",
            )

            row = _base_row(work_id="7633089780427091573")
            row.update(
                {
                    "asr_text_path": str(asr_text_path.resolve()),
                    "asr_provider": "legacy-provider",
                    "asr_model": "legacy-model",
                    "asr_time": "2026-05-01T00:00:00+08:00",
                    "txt_sync_status": "ok",
                    "txt_path": str((tmp / "runtime.txt").resolve()),
                    "dedup_status": "unique",
                }
            )
            repo.upsert_row(row)

            result = _run_script(
                "run_asr_batch.py",
                "--manifest-path",
                str(manifest_path),
                "--reclean-existing",
                "--author",
                "无名书生",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            updated = repo.index_by("work_id")["7633089780427091573"]
            self.assertEqual(updated["asr_status"], "ok")
            self.assertEqual(updated["asr_provider"], "legacy-provider")
            self.assertEqual(updated["asr_model"], "legacy-model")
            self.assertEqual(updated["asr_time"], "2026-05-01T00:00:00+08:00")
            self.assertEqual(updated["txt_sync_status"], "pending")
            self.assertEqual(updated["txt_path"], "")
            self.assertEqual(updated["dedup_status"], "unknown")
            self.assertIn("existing asr text recleaned", updated["notes"])
            self.assertEqual(
                asr_text_path.read_text(encoding="utf-8"),
                "阿尔芒被老亚芒反咬后当场咳血。这是一段足够长的正文内容，用来触发尾部平台标记清理。",
            )

    def test_rewrite_existing_failure_keeps_ok_state_and_records_note(self) -> None:
        schema = load_manifest_schema()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = tmp / "douyin_manifest.csv"
            repo = ManifestRepository(manifest_path, schema)
            repo.init_empty()

            row = _base_row(work_id="7633089780427091574")
            row.update(
                {
                    "asr_text_path": str((tmp / "missing-asr.txt").resolve()),
                    "txt_sync_status": "ok",
                    "txt_path": str((tmp / "runtime.txt").resolve()),
                    "dedup_status": "unique",
                }
            )
            repo.upsert_row(row)

            result = _run_script(
                "run_txt_sync_batch.py",
                "--manifest-path",
                str(manifest_path),
                "--rewrite-existing",
                "--author",
                "无名书生",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            updated = repo.index_by("work_id")["7633089780427091574"]
            self.assertEqual(updated["txt_sync_status"], "ok")
            self.assertEqual(updated["txt_path"], str((tmp / "runtime.txt").resolve()))
            self.assertEqual(updated["dedup_status"], "unique")
            self.assertIn("txt sync rewrite failed:", updated["notes"])


if __name__ == "__main__":
    unittest.main()
