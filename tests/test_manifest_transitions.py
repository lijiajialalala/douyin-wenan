from __future__ import annotations

import unittest

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.manifest.transitions import (
    mark_asr_failed,
    mark_asr_succeeded,
    mark_download_failed,
    mark_download_succeeded,
    reset_download,
    transition_asr,
)


class ManifestTransitionTests(unittest.TestCase):
    def test_reset_download_resets_downstream_state(self) -> None:
        row = {
            "download_status": "ok",
            "download_time": "x",
            "raw_video_path": "video.mp4",
            "raw_audio_path": "audio.wav",
            "asr_status": "ok",
            "asr_provider": "siliconflow",
            "asr_model": "model",
            "asr_time": "x",
            "asr_char_count": "100",
            "asr_chars_per_minute": "200",
            "asr_quality_grade": "B",
            "asr_quality_flags": "",
            "txt_sync_status": "ok",
            "txt_path": "foo.txt",
            "dedup_status": "unique",
            "dedup_group_id": "group-1",
            "notes": "",
        }

        reset_download(row, reason="retry")
        self.assertEqual(row["download_status"], "pending")
        self.assertEqual(row["asr_status"], "pending")
        self.assertEqual(row["txt_sync_status"], "pending")
        self.assertEqual(row["dedup_status"], "unknown")
        self.assertEqual(row["raw_video_path"], "")
        self.assertEqual(row["txt_path"], "")

    def test_asr_ok_requires_download_ok(self) -> None:
        row = {"download_status": "pending", "asr_status": "pending"}
        with self.assertRaises(ValueError):
            transition_asr(row, "ok")

    def test_mark_download_helpers_update_status(self) -> None:
        row = {"download_status": "pending", "raw_video_path": "", "download_time": "", "notes": ""}
        mark_download_succeeded(row, raw_video_path="D:/raw/a.mp4", note="done")
        self.assertEqual(row["download_status"], "ok")
        self.assertEqual(row["raw_video_path"], "D:/raw/a.mp4")

        row = {"download_status": "pending", "raw_video_path": "D:/raw/a.mp4", "notes": ""}
        mark_download_failed(row, reason="boom")
        self.assertEqual(row["download_status"], "failed")
        self.assertEqual(row["raw_video_path"], "")

    def test_mark_asr_helpers_update_status(self) -> None:
        row = {"download_status": "ok", "asr_status": "pending", "notes": ""}
        mark_asr_succeeded(
            row,
            raw_audio_path="D:/audio/a.mp3",
            asr_text_path="C:/tmp/a.txt",
            asr_provider="siliconflow",
            asr_model="SenseVoiceSmall",
            asr_char_count=100,
            asr_chars_per_minute="200.00",
            asr_quality_grade="B",
            asr_quality_flags="",
            note="asr ok",
        )
        self.assertEqual(row["asr_status"], "ok")
        self.assertEqual(row["asr_text_path"], "C:/tmp/a.txt")

        row = {"download_status": "ok", "asr_status": "pending", "notes": ""}
        mark_asr_failed(row, reason="bad audio")
        self.assertEqual(row["asr_status"], "failed")
        self.assertIn("bad audio", row["notes"])


if __name__ == "__main__":
    unittest.main()
