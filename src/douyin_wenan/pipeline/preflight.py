from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreflightCheck:
    code: str
    ok: bool
    message: str


@dataclass(frozen=True)
class PreflightReport:
    stage: str
    checks: tuple[PreflightCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def format_errors(self) -> str:
        return "; ".join(f"{check.code}: {check.message}" for check in self.checks if not check.ok)


def build_download_preflight(*, manifest_path: Path, raw_video_dir: Path) -> PreflightReport:
    checks = (
        _check_manifest_parent(manifest_path),
        _check_directory_writable(raw_video_dir, "raw_video_dir"),
    )
    return PreflightReport(stage="download", checks=checks)


def build_asr_preflight(
    *,
    manifest_path: Path,
    raw_audio_dir: Path,
    asr_text_dir: Path,
    api_key_env: str,
    require_api_key: bool,
    require_ffmpeg: bool,
) -> PreflightReport:
    checks = [
        _check_manifest_parent(manifest_path),
        _check_directory_writable(raw_audio_dir, "raw_audio_dir"),
        _check_directory_writable(asr_text_dir, "asr_text_dir"),
    ]
    if require_api_key:
        checks.append(_check_api_key(api_key_env))
    if require_ffmpeg:
        checks.append(_check_ffmpeg())
    return PreflightReport(stage="asr", checks=tuple(checks))


def build_txt_sync_preflight(*, manifest_path: Path, corpus_dir: Path) -> PreflightReport:
    checks = (
        _check_manifest_parent(manifest_path),
        _check_directory_writable(corpus_dir, "corpus_dir"),
    )
    return PreflightReport(stage="txt_sync", checks=checks)


def assert_preflight(report: PreflightReport) -> None:
    if not report.ok:
        raise ValueError(f"{report.stage} preflight failed: {report.format_errors()}")


def _check_api_key(env_name: str) -> PreflightCheck:
    value = os.getenv(env_name, "").strip()
    if value:
        return PreflightCheck("api_key", True, f"{env_name} is present")
    return PreflightCheck("api_key", False, f"missing required env {env_name}")


def _check_ffmpeg() -> PreflightCheck:
    try:
        import imageio_ffmpeg

        ffmpeg_exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception as exc:
        return PreflightCheck("ffmpeg", False, f"unable to resolve ffmpeg executable: {exc}")
    if ffmpeg_exe.exists():
        return PreflightCheck("ffmpeg", True, str(ffmpeg_exe))
    return PreflightCheck("ffmpeg", False, f"ffmpeg executable does not exist: {ffmpeg_exe}")


def _check_manifest_parent(manifest_path: Path) -> PreflightCheck:
    parent = manifest_path.expanduser().resolve(strict=False).parent
    return _check_directory_writable(parent, "manifest_parent")


def _check_directory_writable(path: Path, code: str) -> PreflightCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".preflight-{uuid.uuid4().hex}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return PreflightCheck(code, True, str(path))
    except Exception as exc:
        return PreflightCheck(code, False, f"{path}: {exc}")
