from __future__ import annotations

import unittest

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.transcribe.quality import grade_transcript


class TranscribeQualityTests(unittest.TestCase):
    def test_grade_transcript_marks_empty_as_d(self) -> None:
        grade, flags, char_count, cpm = grade_transcript("", "120")
        self.assertEqual(grade, "D")
        self.assertIn("empty_transcript", flags)
        self.assertEqual(char_count, 0)
        self.assertEqual(cpm, "")

    def test_grade_transcript_returns_b_for_normal_density(self) -> None:
        text = "这是一个正常长度的转写文本。" * 30
        grade, flags, char_count, cpm = grade_transcript(text, "300")
        self.assertEqual(grade, "B")
        self.assertEqual(flags, "")
        self.assertTrue(char_count > 0)
        self.assertTrue(cpm)


if __name__ == "__main__":
    unittest.main()
