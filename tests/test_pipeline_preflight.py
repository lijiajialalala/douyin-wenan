from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.pipeline.preflight import build_asr_preflight, build_download_preflight


class PipelinePreflightTests(unittest.TestCase):
    def test_download_preflight_checks_manifest_parent_and_video_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            report = build_download_preflight(
                manifest_path=tmp / "manifest" / "douyin_manifest.csv",
                raw_video_dir=tmp / "raw_videos",
            )
        self.assertTrue(report.ok)

    def test_asr_preflight_requires_api_key_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with patch.dict(os.environ, {}, clear=True):
                fake_module = SimpleNamespace(get_ffmpeg_exe=lambda: str((tmp / "ffmpeg.exe").resolve()))
                with patch.dict(sys.modules, {"imageio_ffmpeg": fake_module}):
                    (tmp / "ffmpeg.exe").write_text("binary", encoding="utf-8")
                    report = build_asr_preflight(
                        manifest_path=tmp / "manifest" / "douyin_manifest.csv",
                        raw_audio_dir=tmp / "raw_audio",
                        asr_text_dir=tmp / "asr_text",
                        api_key_env="SILICONFLOW_API_KEY",
                        require_api_key=True,
                        require_ffmpeg=True,
                    )
        self.assertFalse(report.ok)
        self.assertIn("api_key", report.format_errors())


if __name__ == "__main__":
    unittest.main()
