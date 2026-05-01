from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg

from douyin_wenan.paths import ensure_parent_dir


def extract_audio_for_asr(*, raw_video_path: Path, raw_audio_dir: Path, author: str, work_id: str) -> Path:
    output_path = raw_audio_dir / author / f"{work_id}.mp3"
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    ensure_parent_dir(output_path)
    temp_path = output_path.with_name(output_path.stem + ".part" + output_path.suffix)
    if temp_path.exists():
        temp_path.unlink()

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(raw_video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(temp_path),
    ]
    completed = subprocess.run(command, capture_output=True)
    if completed.returncode != 0:
        if temp_path.exists():
            temp_path.unlink()
        stderr_text = (completed.stderr or b"").decode("utf-8", errors="ignore").strip()
        stdout_text = (completed.stdout or b"").decode("utf-8", errors="ignore").strip()
        detail = stderr_text or stdout_text or "ffmpeg audio extraction failed"
        short_detail = detail.splitlines()[-1].strip() if detail.splitlines() else detail
        raise ValueError(f"ffmpeg audio extraction failed: {short_detail}")
    if not temp_path.exists() or temp_path.stat().st_size <= 0:
        raise ValueError("ffmpeg produced no audio output")

    temp_path.replace(output_path)
    return output_path
