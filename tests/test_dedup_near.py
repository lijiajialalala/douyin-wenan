from __future__ import annotations

import unittest

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.dedup.near import classify_against_existing, normalize_text


class DedupNearTests(unittest.TestCase):
    def test_normalize_text_removes_whitespace(self) -> None:
        self.assertEqual(normalize_text("你 好 \n 世 界"), "你好世界")

    def test_exact_duplicate_becomes_duplicate(self) -> None:
        decision = classify_against_existing(
            work_id="a",
            text="你好 世界",
            existing_items=[("b", "你好世界")],
        )
        self.assertEqual(decision.status, "duplicate")
        self.assertEqual(decision.group_id, "dup-b")

    def test_different_text_becomes_unique(self) -> None:
        decision = classify_against_existing(
            work_id="a",
            text="你好世界",
            existing_items=[("b", "完全不同的文本")],
        )
        self.assertEqual(decision.status, "unique")


if __name__ == "__main__":
    unittest.main()
