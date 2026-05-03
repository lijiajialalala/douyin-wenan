from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.normalize.txt_writer import (
    build_standard_txt_path,
    format_transcript_body,
    is_runtime_transcript_path,
    primary_title_segment,
    render_standard_transcript,
    sanitize_title_for_filename,
)


class TxtWriterTests(unittest.TestCase):
    def test_build_standard_txt_path_uses_existing_path_when_present(self) -> None:
        path = build_standard_txt_path(
            corpus_root=Path("D:/runtime/corpus"),
            author="无名书生",
            work_id="123",
            title="标题A",
            existing_txt_path="D:/runtime/corpus/无名书生/transcripts/123_标题A.txt",
        )
        self.assertEqual(path, Path("D:/runtime/corpus/无名书生/transcripts/123_标题A.txt"))

    def test_build_standard_txt_path_generates_author_scoped_file(self) -> None:
        path = build_standard_txt_path(
            corpus_root=Path("D:/runtime/corpus"),
            author="无名书生",
            work_id="123",
            title="#茶花女 的破产清算：捞女经济学的死亡螺旋",
            existing_txt_path="",
        )
        self.assertEqual(path, Path("D:/runtime/corpus/无名书生/transcripts/123_茶花女的破产清算.txt"))

    def test_render_standard_transcript_contains_body_and_counts(self) -> None:
        row = {
            "title": "标题A",
            "author": "无名书生",
            "work_id": "123",
            "followers": "1000",
            "account_link": "https://example.com/u/1",
            "video_link": "https://example.com/v/1",
            "publish_time": "2026-05-01 12:00",
            "duration_text": "00:30",
            "likes": "10",
            "comments": "1",
            "favorites": "2",
            "shares": "3",
            "raw_video_path": "D:/raw/123.mp4",
            "asr_provider": "siliconflow",
            "asr_quality_grade": "B",
            "manual_reviewed": "no",
        }
        content = render_standard_transcript(row, "你好？你好。")
        self.assertIn("标题：标题A", content)
        self.assertIn("文案字数：6", content)
        self.assertIn("疑问句数：1", content)
        self.assertIn("正文文案：\n你好？你好。", content)
        self.assertNotIn("正文总结：", content)
        self.assertNotIn("整理状态：", content)

    def test_sanitize_title_for_filename_removes_invalid_chars(self) -> None:
        self.assertEqual(sanitize_title_for_filename('#茶花女 的破产清算：捞女经济学'), "茶花女的破产清算")

    def test_primary_title_segment_and_runtime_path_rule(self) -> None:
        self.assertEqual(primary_title_segment("#茶花女 的破产清算：捞女经济学"), "茶花女 的破产清算")
        self.assertTrue(
            is_runtime_transcript_path(
                Path("D:/runtime/corpus/无名书生/transcripts/123_茶花女.txt"),
                corpus_root=Path("D:/runtime/corpus"),
            )
        )
        self.assertFalse(
            is_runtime_transcript_path(
                Path("D:/legacy/无名书生/整理版/01_无名书生_作品_1.txt"),
                corpus_root=Path("D:/runtime/corpus"),
            )
        )

    def test_format_transcript_body_wraps_long_text_by_sentence(self) -> None:
        formatted = format_transcript_body("第一句。第二句。第三句。", target_paragraph_chars=4)
        self.assertEqual(formatted, "第一句。\n第二句。\n第三句。")


if __name__ == "__main__":
    unittest.main()
