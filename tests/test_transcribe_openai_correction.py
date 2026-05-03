from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.transcribe.openai_correction import (
    OpenAICorrectionResult,
    OpenAICorrectionRejected,
    build_api_url,
    correct_transcript_text,
)
from douyin_wenan.transcribe.postprocess import process_transcript_text


class OpenAICorrectionTests(unittest.TestCase):
    def test_build_api_url_accepts_base_with_or_without_v1(self) -> None:
        self.assertEqual(build_api_url("http://localhost:48760", "/v1/chat/completions"), "http://localhost:48760/v1/chat/completions")
        self.assertEqual(build_api_url("http://localhost:48760/v1", "/v1/chat/completions"), "http://localhost:48760/v1/chat/completions")

    @patch("douyin_wenan.transcribe.openai_correction.requests.post")
    def test_correct_transcript_text_parses_json_response(self, mock_post: MagicMock) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "final_text": "他当场咳血。",
                                "edits": [
                                    {
                                        "from": "科血",
                                        "to": "咳血",
                                        "reason": "明显同音误识别",
                                        "confidence": 0.98,
                                    }
                                ],
                                "needs_review": False,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        mock_post.return_value = response

        result = correct_transcript_text(
            transcript_text="他当场科血。",
            api_key="secret",
            base_url="http://localhost:48760/v1",
            model="gpt-test",
        )

        self.assertEqual(result.final_text, "他当场咳血。")
        self.assertEqual(len(result.edits), 1)
        self.assertEqual(result.edits[0]["from"], "科血")
        self.assertEqual(result.edits[0]["to"], "咳血")
        self.assertFalse(result.needs_review)

    @patch("douyin_wenan.transcribe.openai_correction.requests.post")
    def test_correct_transcript_text_prefers_utf8_content_when_provider_charset_is_wrong(self, mock_post: MagicMock) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "final_text": "他当场咳血。",
                                "edits": [{"from": "科血", "to": "咳血"}],
                                "needs_review": False,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "{\"final_text\":\"ä»å½åºå³è¡ã\",\"edits\":[],\"needs_review\":false}"
                    }
                }
            ]
        }
        mock_post.return_value = response

        result = correct_transcript_text(
            transcript_text="他当场科血。",
            api_key="secret",
            base_url="https://leleapi.top",
            model="gpt-5.5",
        )

        self.assertEqual(result.final_text, "他当场咳血。")
        self.assertEqual(result.edits[0]["from"], "科血")
        self.assertEqual(result.edits[0]["to"], "咳血")

    @patch("douyin_wenan.transcribe.openai_correction.requests.post")
    def test_correct_transcript_text_rejects_large_rewrite(self, mock_post: MagicMock) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "final_text": "这是完全重写后的总结性文案，不再保留原始口播结构。",
                                "edits": [{"from": "原文", "to": "总结", "reason": "错误", "confidence": 0.8}],
                                "needs_review": False,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        mock_post.return_value = response

        with self.assertRaises(ValueError):
            correct_transcript_text(
                transcript_text="原文很短。",
                api_key="secret",
                base_url="http://localhost:48760/v1",
                model="gpt-test",
            )

    @patch("douyin_wenan.transcribe.openai_correction.requests.post")
    def test_correct_transcript_text_allows_low_density_edits_for_long_transcript(self, mock_post: MagicMock) -> None:
        transcript_text = "古希腊神谱。" * 1400
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "final_text": transcript_text,
                                "edits": [{"value": f"edit-{index}"} for index in range(46)],
                                "needs_review": True,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        mock_post.return_value = response

        result = correct_transcript_text(
            transcript_text=transcript_text,
            api_key="secret",
            base_url="https://leleapi.top",
            model="gpt-5.5",
        )

        self.assertEqual(result.final_text, transcript_text)
        self.assertEqual(len(result.edits), 46)
        self.assertTrue(result.needs_review)

    @patch("douyin_wenan.transcribe.openai_correction.requests.post")
    def test_correct_transcript_text_preserves_candidate_payload_when_edits_exceed_limit(self, mock_post: MagicMock) -> None:
        transcript_text = "短文本。" * 20
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "final_text": transcript_text,
                                "edits": [{"value": f"edit-{index}"} for index in range(41)],
                                "needs_review": False,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
        mock_post.return_value = response

        with self.assertRaises(OpenAICorrectionRejected) as ctx:
            correct_transcript_text(
                transcript_text=transcript_text,
                api_key="secret",
                base_url="https://leleapi.top",
                model="gpt-5.5",
            )

        self.assertEqual(ctx.exception.candidate_final_text, transcript_text)
        self.assertEqual(len(ctx.exception.candidate_edits), 41)
        self.assertFalse(ctx.exception.candidate_needs_review)


class TranscriptPostprocessTests(unittest.TestCase):
    def test_process_transcript_text_preserves_raw_and_writes_corrected_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            result = process_transcript_text(
                raw_text="🎼他当场科血。抖音。",
                raw_text_path=tmp / "raw.txt",
                final_text_path=tmp / "final.txt",
                correction_json_path=tmp / "correction.json",
                correction_runner=lambda normalized: OpenAICorrectionResult(
                    final_text="他当场咳血。",
                    edits=[{"from": "科血", "to": "咳血", "reason": "明显同音误识别", "confidence": 0.98}],
                    needs_review=False,
                    raw_response_text="{}",
                ),
            )

            self.assertEqual((tmp / "raw.txt").read_text(encoding="utf-8"), "🎼他当场科血。抖音。")
            self.assertEqual((tmp / "final.txt").read_text(encoding="utf-8"), "他当场咳血。")
            audit = json.loads((tmp / "correction.json").read_text(encoding="utf-8"))
            self.assertEqual(audit["final_text"], "他当场咳血。")
            self.assertEqual(audit["edits"][0]["from"], "科血")
            self.assertTrue(result.correction_applied)

    def test_process_transcript_text_falls_back_to_safe_normalized_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            result = process_transcript_text(
                raw_text="🎼他当场科血。抖音。",
                raw_text_path=tmp / "raw.txt",
                final_text_path=tmp / "final.txt",
                correction_json_path=tmp / "correction.json",
                correction_runner=lambda normalized: (_ for _ in ()).throw(ValueError("bad correction")),
            )

            self.assertEqual((tmp / "final.txt").read_text(encoding="utf-8"), "他当场科血。抖音。")
            self.assertFalse(result.correction_applied)
            self.assertIn("bad correction", result.note)

    def test_process_transcript_text_persists_rejected_candidate_in_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            result = process_transcript_text(
                raw_text="他当场科血。",
                raw_text_path=tmp / "raw.txt",
                final_text_path=tmp / "final.txt",
                correction_json_path=tmp / "correction.json",
                correction_runner=lambda normalized: (_ for _ in ()).throw(
                    OpenAICorrectionRejected(
                        "too many edits",
                        candidate_final_text="他当场咳血。",
                        candidate_edits=[{"from": "科血", "to": "咳血"}],
                        candidate_needs_review=True,
                        raw_response_text='{"final_text":"他当场咳血。"}',
                    )
                ),
            )

            audit = json.loads((tmp / "correction.json").read_text(encoding="utf-8"))
            self.assertEqual((tmp / "final.txt").read_text(encoding="utf-8"), "他当场科血。")
            self.assertFalse(result.correction_applied)
            self.assertEqual(audit["candidate"]["final_text"], "他当场咳血。")
            self.assertEqual(audit["candidate"]["edits"][0]["from"], "科血")
            self.assertTrue(audit["candidate"]["needs_review"])
