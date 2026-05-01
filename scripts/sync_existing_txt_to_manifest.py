#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from _bootstrap import configure_stdio, ensure_src_path
except ModuleNotFoundError:
    from scripts._bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.common.ids import extract_video_id, synthetic_work_id
from douyin_wenan.common.text_io import compact_char_count, parse_transcript_header
from douyin_wenan.config import load_runtime_config
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema
from douyin_wenan.paths import iter_standard_transcript_files


PROVIDER_MARKERS = {
    "siliconflow": "siliconflow",
    "openai": "openai",
    "faster-whisper": "local_whisper",
    "local": "local_whisper",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill manifest rows from existing standardized txt files.")
    parser.add_argument("--config", type=Path, default=None, help="Path to local config yaml")
    parser.add_argument("--legacy-input-root", type=Path, default=None, help="Override legacy input root directory")
    parser.add_argument("--project-root", type=Path, default=None, help="Deprecated alias for --legacy-input-root")
    parser.add_argument("--manifest-path", type=Path, default=None, help="Override manifest file path")
    parser.add_argument("--author", type=str, default="", help="Only process one author directory")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N transcript files")
    return parser.parse_args()


def normalize_provider(status_text: str) -> str:
    lowered = (status_text or "").strip().lower()
    for marker, provider in PROVIDER_MARKERS.items():
        if marker in lowered:
            return provider
    return ""


def infer_manual_reviewed(meta: dict[str, str]) -> str:
    value = (meta.get("是否人工校对", "") or "").strip()
    if value in {"是", "yes", "Yes", "YES"}:
        return "yes"
    status = (meta.get("整理状态", "") or "").strip()
    if "未人工校对" in status:
        return "no"
    return "no"


def build_backfill_row(txt_path: Path, meta: dict[str, str], body: str) -> dict[str, str] | None:
    title = (meta.get("标题", "") or "").strip()
    author = (meta.get("作者", "") or txt_path.parts[-3]).strip()
    video_link = (meta.get("视频链接", "") or "").strip()
    if not title or not video_link:
        return None

    work_id = (meta.get("作品ID", "") or "").strip()
    if not work_id:
        work_id = extract_video_id(video_link) or synthetic_work_id(
            author=author,
            publish_time=(meta.get("发布时间", "") or "").strip(),
            title=title,
            video_link=video_link,
        )

    provider = normalize_provider(meta.get("整理状态", "") or meta.get("ASR来源", ""))
    row = {
        "work_id": work_id,
        "author": author,
        "platform": ((meta.get("平台", "") or "抖音").strip() or "抖音").lower().replace("抖音", "douyin"),
        "video_link": video_link,
        "account_link": (meta.get("账号链接", "") or "").strip(),
        "title": title,
        "publish_time": (meta.get("发布时间", "") or "").strip(),
        "duration_text": (meta.get("时长", "") or "").strip(),
        "duration_seconds": "",
        "likes": _normalize_int_text(meta.get("点赞", "")),
        "comments": _normalize_int_text(meta.get("评论", "")),
        "favorites": _normalize_int_text(meta.get("收藏", "")),
        "shares": _normalize_int_text(meta.get("转发", "")),
        "followers": _normalize_int_text(meta.get("粉丝数", "")),
        "raw_video_path": "",
        "raw_audio_path": "",
        "asr_text_path": "",
        "legacy_txt_path": str(txt_path.resolve()),
        "txt_path": "",
        "download_status": "pending",
        "download_time": "",
        "asr_provider": provider,
        "asr_model": "",
        "asr_time": "",
        "asr_status": "pending",
        "asr_char_count": "",
        "asr_chars_per_minute": "",
        "asr_quality_grade": "",
        "asr_quality_flags": "",
        "manual_reviewed": infer_manual_reviewed(meta),
        "txt_sync_status": "pending",
        "dedup_status": "unknown",
        "dedup_group_id": "",
        "notes": "backfilled from legacy txt",
    }
    if body:
        row["notes"] = f"{row['notes']} | legacy body chars={compact_char_count(body)}"

    duration_seconds = _parse_duration_seconds(row["duration_text"])
    if duration_seconds is not None:
        row["duration_seconds"] = str(duration_seconds)
    return row


def merge_row(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    merged = dict(existing)

    for field in [
        "author",
        "platform",
        "video_link",
        "account_link",
        "title",
        "publish_time",
        "duration_text",
        "duration_seconds",
        "likes",
        "comments",
        "favorites",
        "shares",
        "followers",
        "legacy_txt_path",
        "asr_provider",
        "manual_reviewed",
    ]:
        incoming_value = (incoming.get(field, "") or "").strip()
        if incoming_value and not (merged.get(field, "") or "").strip():
            merged[field] = incoming_value

    # Strong content evidence from txt can refresh these fields.
    for field in ["title", "publish_time", "account_link"]:
        incoming_value = (incoming.get(field, "") or "").strip()
        if incoming_value:
            merged[field] = incoming_value

    merged["legacy_txt_path"] = incoming["legacy_txt_path"]

    if not (merged.get("notes", "") or "").strip():
        merged["notes"] = incoming["notes"]
    elif incoming["notes"] not in merged["notes"]:
        merged["notes"] = f"{merged['notes']} | {incoming['notes']}"

    return merged


def _normalize_int_text(value: str) -> str:
    text = (value or "").strip().replace(",", "")
    if not text:
        return ""
    try:
        if text.endswith("万"):
            number = float(text[:-1]) * 10000
            return str(int(round(number)))
        if text.endswith("亿"):
            number = float(text[:-1]) * 100000000
            return str(int(round(number)))
        return str(int(round(float(text))))
    except ValueError:
        return ""


def _parse_duration_seconds(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if not all(part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    if len(numbers) == 3:
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    return None


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    legacy_input_root = args.legacy_input_root or args.project_root or config.legacy_input_root
    manifest_path = args.manifest_path or config.manifest_path

    schema = load_manifest_schema()
    repo = ManifestRepository(manifest_path, schema)
    repo.init_empty(overwrite=False)
    repo.migrate_to_schema()

    rows_by_work_id = repo.index_by("work_id")
    transcript_files = iter_standard_transcript_files(legacy_input_root, author=args.author)
    if args.limit > 0:
        transcript_files = transcript_files[: args.limit]

    created = 0
    updated = 0
    skipped = 0

    for txt_path in transcript_files:
        meta, body = parse_transcript_header(txt_path)
        candidate = build_backfill_row(txt_path, meta, body)
        if candidate is None:
            skipped += 1
            continue

        work_id = candidate["work_id"]
        existing = rows_by_work_id.get(work_id)
        if existing is None:
            repo.upsert_row(candidate)
            rows_by_work_id[work_id] = candidate
            created += 1
        else:
            merged = merge_row(existing, candidate)
            repo.upsert_row(merged)
            rows_by_work_id[work_id] = merged
            updated += 1

    print(manifest_path)
    print(f"created={created}")
    print(f"updated={updated}")
    print(f"skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
