from __future__ import annotations

import unittest

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.transcribe.cleaning import clean_transcript_text


class TranscribeCleaningTests(unittest.TestCase):
    def test_clean_transcript_text_removes_music_markers_and_emoji(self) -> None:
        cleaned = clean_transcript_text("🎼你好😊 [音乐] 世界♪")
        self.assertEqual(cleaned, "你好 世界")

    def test_clean_transcript_text_does_not_apply_global_word_replacements(self) -> None:
        source = "阿尔蒙被老鸭毛反咬后当场科血。肺结和晚期的她背着一个网袋回家。"
        cleaned = clean_transcript_text(source)
        self.assertEqual(cleaned, source)

    def test_clean_transcript_text_keeps_bare_content_words(self) -> None:
        cleaned = clean_transcript_text("他是这段旁白的作者。观众的笑声其实是表演的一部分。")
        self.assertEqual(cleaned, "他是这段旁白的作者。观众的笑声其实是表演的一部分。")

    def test_clean_transcript_text_strips_trailing_douyin_marker(self) -> None:
        cleaned = clean_transcript_text("这是一段很长的正文内容，最后不该带平台标记。 抖音。")
        self.assertFalse(cleaned.endswith("抖音。"))


if __name__ == "__main__":
    unittest.main()
