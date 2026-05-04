from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema
from douyin_wenan.normalize.txt_writer import render_standard_transcript, write_standard_transcript


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, f"scripts/{script_name}", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _write_config(path: Path, *, manifest_path: Path, runtime_root: Path) -> None:
    path.write_text(
        "\n".join(
            [
                f'legacy_input_root: "{(runtime_root / "legacy").as_posix()}"',
                f'runtime_root: "{runtime_root.as_posix()}"',
                "runtime:",
                f'  manifest_path: "{manifest_path.as_posix()}"',
                f'  source_links_dir: "{(runtime_root / "ingest" / "source_links").as_posix()}"',
                f'  raw_video_dir: "{(runtime_root / "assets" / "raw_videos").as_posix()}"',
                f'  raw_audio_dir: "{(runtime_root / "assets" / "raw_audio").as_posix()}"',
                f'  asr_text_dir: "{(runtime_root / "snapshots" / "asr_text").as_posix()}"',
                f'  corpus_dir: "{(runtime_root / "corpus").as_posix()}"',
                f'  analysis_dir: "{(runtime_root / "analysis").as_posix()}"',
                f'  logs_dir: "{(runtime_root / "logs").as_posix()}"',
                "asr:",
                '  provider: "siliconflow"',
                '  model: "FunAudioLLM/SenseVoiceSmall"',
                '  base_url: "https://api.siliconflow.cn"',
                '  api_key_env: "SILICONFLOW_API_KEY"',
                "correction:",
                '  enabled: "false"',
                '  provider: "openai"',
                '  model: "gpt-5.5"',
                '  base_url: "https://api.openai.com"',
                '  api_key_env: "OPENAI_API_KEY"',
            ]
        ),
        encoding="utf-8",
    )


class LegacyTxtBatchTests(unittest.TestCase):
    def test_run_legacy_txt_batch_imports_runtime_transcript_from_legacy_source(self) -> None:
        schema = load_manifest_schema()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            runtime_root = tmp / "runtime"
            manifest_path = runtime_root / "manifest" / "douyin_manifest.csv"
            config_path = tmp / "local.yaml"
            _write_config(config_path, manifest_path=manifest_path, runtime_root=runtime_root)

            legacy_dir = tmp / "legacy"
            legacy_txt_path = legacy_dir / "sample.txt"
            legacy_row = {
                "title": "世界的本原是什么",
                "author": "柏拉图的石头",
                "work_id": "7164997074918837516",
                "followers": "1000",
                "account_link": "https://example.com/u/1",
                "video_link": "https://www.douyin.com/video/7164997074918837516",
                "publish_time": "2026-05-03 12:00",
                "duration_text": "03:30",
                "likes": "200",
                "comments": "20",
                "favorites": "30",
                "shares": "15",
                "raw_video_path": "",
                "asr_provider": "",
                "asr_quality_grade": "",
                "manual_reviewed": "yes",
            }
            body = "世界的本原是什么？这是古希腊人在哲学上的第一次追问。"
            write_standard_transcript(
                output_path=legacy_txt_path,
                content=render_standard_transcript(legacy_row, body),
            )

            repo = ManifestRepository(manifest_path, schema)
            repo.init_empty()
            row = schema.make_default_row()
            row.update(
                {
                    "work_id": "7164997074918837516",
                    "author": "柏拉图的石头",
                    "platform": "douyin",
                    "video_link": "https://www.douyin.com/video/7164997074918837516",
                    "account_link": "https://example.com/u/1",
                    "title": "世界的本原是什么",
                    "publish_time": "2026-05-03 12:00",
                    "duration_text": "03:30",
                    "likes": "200",
                    "comments": "20",
                    "favorites": "30",
                    "shares": "15",
                    "followers": "1000",
                    "legacy_txt_path": str(legacy_txt_path.resolve()),
                    "manual_reviewed": "yes",
                }
            )
            repo.upsert_row(row)

            result = _run_script(
                "run_legacy_txt_batch.py",
                "--config",
                str(config_path),
                "--author",
                "柏拉图的石头",
                "--skip-preflight",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("succeeded=1", result.stdout)
            updated = repo.index_by("work_id")["7164997074918837516"]
            self.assertEqual(updated["download_status"], "pending")
            self.assertEqual(updated["asr_status"], "pending")
            self.assertEqual(updated["txt_sync_status"], "ok")
            self.assertEqual(updated["dedup_status"], "unknown")
            runtime_txt_path = Path(updated["txt_path"])
            self.assertTrue(runtime_txt_path.exists())
            self.assertIn(str(runtime_root / "corpus"), str(runtime_txt_path))
            content = runtime_txt_path.read_text(encoding="utf-8")
            self.assertIn("正文文案：", content)
            self.assertIn(body, content)


if __name__ == "__main__":
    unittest.main()
