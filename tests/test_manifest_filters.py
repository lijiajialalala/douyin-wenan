from __future__ import annotations

import unittest

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.manifest.filters import (
    select_asr_completed,
    select_asr_pending,
    select_asr_reprocessable,
    select_asr_retryable,
    select_dedup_pending,
    select_download_pending,
    select_download_retryable,
    select_txt_sync_rebuildable,
    select_txt_sync_pending,
)


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "work_id": "w",
        "author": "作者A",
        "title": "标题",
        "video_link": "https://example.com/video",
        "raw_video_path": "",
        "asr_text_path": "",
        "txt_path": "",
        "download_status": "pending",
        "download_failure_count": "0",
        "download_failure_class": "",
        "asr_status": "pending",
        "asr_failure_count": "0",
        "asr_failure_class": "",
        "txt_sync_status": "pending",
        "dedup_status": "unknown",
    }
    row.update(overrides)
    return row


class ManifestFiltersTests(unittest.TestCase):
    def test_select_download_pending_requires_video_link(self) -> None:
        rows = [
            _row(work_id="ok-1"),
            _row(work_id="skip-1", video_link="", download_status="pending"),
            _row(work_id="skip-2", download_status="ok"),
        ]
        selected = select_download_pending(rows)
        self.assertEqual([row["work_id"] for row in selected], ["ok-1"])

    def test_select_asr_pending_respects_author_and_limit(self) -> None:
        rows = [
            _row(work_id="a-1", author="无名书生", download_status="ok", asr_status="pending"),
            _row(work_id="a-2", author="无名书生", download_status="ok", asr_status="pending"),
            _row(work_id="b-1", author="一代书生", download_status="ok", asr_status="pending"),
        ]
        selected = select_asr_pending(rows, author="无名书生", limit=1)
        self.assertEqual([row["work_id"] for row in selected], ["a-1"])

    def test_select_download_retryable_requires_failed_status(self) -> None:
        rows = [
            _row(work_id="retry-1", download_status="failed"),
            _row(work_id="skip-1", download_status="pending"),
            _row(work_id="skip-2", download_status="failed", video_link=""),
        ]
        selected = select_download_retryable(rows)
        self.assertEqual([row["work_id"] for row in selected], ["retry-1"])

    def test_select_download_retryable_skips_blocked_and_exhausted_failures(self) -> None:
        rows = [
            _row(work_id="retry-1", download_status="failed", download_failure_class="retryable", download_failure_count="1"),
            _row(work_id="skip-1", download_status="failed", download_failure_class="blocked", download_failure_count="1"),
            _row(work_id="skip-2", download_status="failed", download_failure_class="retryable", download_failure_count="2"),
        ]
        selected = select_download_retryable(rows, max_failure_count=2)
        self.assertEqual([row["work_id"] for row in selected], ["retry-1"])

    def test_select_asr_completed_requires_asr_text_path(self) -> None:
        rows = [
            _row(work_id="ok-1", asr_status="ok", asr_text_path="C:/tmp/1.txt"),
            _row(work_id="skip-1", asr_status="ok", asr_text_path=""),
            _row(work_id="skip-2", asr_status="pending", asr_text_path="C:/tmp/2.txt"),
        ]
        selected = select_asr_completed(rows)
        self.assertEqual([row["work_id"] for row in selected], ["ok-1"])

    def test_select_asr_reprocessable_requires_downloaded_video(self) -> None:
        rows = [
            _row(work_id="skip-1", download_status="ok", asr_status="ok", raw_video_path=""),
            _row(work_id="skip-2", download_status="pending", asr_status="ok", raw_video_path="D:/raw/2.mp4"),
            _row(work_id="ok-1", download_status="ok", asr_status="ok", raw_video_path="D:/raw/1.mp4"),
        ]
        selected = select_asr_reprocessable(rows)
        self.assertEqual([row["work_id"] for row in selected], ["ok-1"])

    def test_select_asr_retryable_requires_failed_status_and_download_ok(self) -> None:
        rows = [
            _row(work_id="retry-1", download_status="ok", asr_status="failed"),
            _row(work_id="skip-1", download_status="pending", asr_status="failed"),
            _row(work_id="skip-2", download_status="ok", asr_status="pending"),
        ]
        selected = select_asr_retryable(rows)
        self.assertEqual([row["work_id"] for row in selected], ["retry-1"])

    def test_select_asr_retryable_skips_blocked_failures_by_default(self) -> None:
        rows = [
            _row(work_id="retry-1", download_status="ok", asr_status="failed", asr_failure_class="retryable", asr_failure_count="1"),
            _row(work_id="skip-1", download_status="ok", asr_status="failed", asr_failure_class="blocked", asr_failure_count="1"),
        ]
        selected = select_asr_retryable(rows)
        self.assertEqual([row["work_id"] for row in selected], ["retry-1"])

    def test_select_txt_sync_pending_requires_asr_ok(self) -> None:
        rows = [
            _row(work_id="ok-1", asr_status="ok", txt_sync_status="pending", asr_text_path="C:/tmp/1.txt"),
            _row(work_id="skip-1", asr_status="pending", txt_sync_status="pending", asr_text_path="C:/tmp/2.txt"),
            _row(work_id="skip-2", asr_status="ok", txt_sync_status="pending", asr_text_path=""),
        ]
        selected = select_txt_sync_pending(rows)
        self.assertEqual([row["work_id"] for row in selected], ["ok-1"])

    def test_select_txt_sync_rebuildable_ignores_txt_sync_status(self) -> None:
        rows = [
            _row(work_id="ok-1", asr_status="ok", txt_sync_status="ok", asr_text_path="C:/tmp/1.txt"),
            _row(work_id="ok-2", asr_status="ok", txt_sync_status="pending", asr_text_path="C:/tmp/2.txt"),
            _row(work_id="skip-1", asr_status="pending", txt_sync_status="ok", asr_text_path="C:/tmp/3.txt"),
        ]
        selected = select_txt_sync_rebuildable(rows)
        self.assertEqual([row["work_id"] for row in selected], ["ok-1", "ok-2"])

    def test_select_dedup_pending_requires_txt_sync_and_txt_path(self) -> None:
        rows = [
            _row(work_id="ok-1", txt_sync_status="ok", dedup_status="unknown", txt_path="C:/tmp/1.txt"),
            _row(work_id="skip-1", txt_sync_status="ok", dedup_status="unknown", txt_path=""),
            _row(work_id="skip-2", txt_sync_status="pending", dedup_status="unknown", txt_path="C:/tmp/2.txt"),
        ]
        selected = select_dedup_pending(rows)
        self.assertEqual([row["work_id"] for row in selected], ["ok-1"])


if __name__ == "__main__":
    unittest.main()
