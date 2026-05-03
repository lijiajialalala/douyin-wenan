from __future__ import annotations

import unittest

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.pipeline.failures import classify_asr_failure, classify_download_failure, hydrate_failure_metadata


class PipelineFailureTests(unittest.TestCase):
    def test_download_404_becomes_terminal(self) -> None:
        decision = classify_download_failure("404 Client Error: Not Found for url: https://example.com/video.mp4")
        self.assertEqual(decision.failure_class, "terminal")
        self.assertEqual(decision.failure_code, "http_404")

    def test_download_500_becomes_retryable(self) -> None:
        decision = classify_download_failure("500 Server Error: Internal Server Error for url: https://example.com/video.mp4")
        self.assertEqual(decision.failure_class, "retryable")
        self.assertEqual(decision.failure_code, "http_500")

    def test_asr_missing_key_becomes_blocked(self) -> None:
        decision = classify_asr_failure("Missing required API key env: SILICONFLOW_API_KEY")
        self.assertEqual(decision.failure_class, "blocked")
        self.assertEqual(decision.failure_code, "missing_api_key")

    def test_asr_timeout_becomes_retryable(self) -> None:
        decision = classify_asr_failure("HTTPSConnectionPool(host='api.siliconflow.cn', port=443): Read timed out.")
        self.assertEqual(decision.failure_class, "retryable")
        self.assertEqual(decision.failure_code, "network_timeout")

    def test_hydrate_failure_metadata_backfills_legacy_notes(self) -> None:
        row = {
            "download_status": "failed",
            "download_failure_count": "",
            "download_failure_class": "",
            "download_failure_code": "",
            "asr_status": "pending",
            "asr_failure_count": "",
            "asr_failure_class": "",
            "asr_failure_code": "",
            "notes": "download failed: 403 Client Error: Forbidden for url: https://example.com/video.mp4",
        }
        changed = hydrate_failure_metadata(row)
        self.assertTrue(changed)
        self.assertEqual(row["download_failure_class"], "blocked")
        self.assertEqual(row["download_failure_code"], "http_403")
        self.assertEqual(row["download_failure_count"], "1")


if __name__ == "__main__":
    unittest.main()
