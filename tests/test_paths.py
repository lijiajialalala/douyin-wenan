from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.paths import iter_author_dirs, iter_standard_transcript_files


class PathsTests(unittest.TestCase):
    def test_iter_author_dirs_can_filter_one_author(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "无名书生" / "整理版").mkdir(parents=True)
            (root / "一代书生" / "整理版").mkdir(parents=True)
            (root / "_assets").mkdir()

            author_dirs = iter_author_dirs(root, author="无名书生")

            self.assertEqual([path.name for path in author_dirs], ["无名书生"])

    def test_iter_standard_transcript_files_only_returns_numeric_txt_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tidy_dir = Path(tmpdir) / "无名书生" / "整理版"
            tidy_dir.mkdir(parents=True)
            (tidy_dir / "01_样本.txt").write_text("x", encoding="utf-8")
            (tidy_dir / "readme.txt").write_text("x", encoding="utf-8")

            files = iter_standard_transcript_files(Path(tmpdir), author="无名书生")

            self.assertEqual([path.name for path in files], ["01_样本.txt"])


if __name__ == "__main__":
    unittest.main()
