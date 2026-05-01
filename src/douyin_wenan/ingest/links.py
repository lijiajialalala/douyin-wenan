from __future__ import annotations

import csv
from pathlib import Path

from douyin_wenan.common.ids import extract_video_id, synthetic_work_id


REQUIRED_SOURCE_FIELDS = ("author", "video_link", "title")
OPTIONAL_SOURCE_FIELDS = (
    "account_link",
    "publish_time",
    "duration_text",
    "likes",
    "comments",
    "favorites",
    "shares",
    "followers",
    "notes",
)


def build_link_row(source: dict[str, str]) -> dict[str, str]:
    author = _required_text(source, "author")
    video_link = _required_text(source, "video_link")
    title = _required_text(source, "title")
    work_id = extract_video_id(video_link) or synthetic_work_id(
        author=author,
        publish_time=(source.get("publish_time", "") or "").strip(),
        title=title,
        video_link=video_link,
    )

    row = {
        "work_id": work_id,
        "author": author,
        "platform": "douyin",
        "video_link": video_link,
        "account_link": _text(source, "account_link"),
        "title": title,
        "publish_time": _text(source, "publish_time"),
        "duration_text": _text(source, "duration_text"),
        "duration_seconds": "",
        "likes": _normalize_int_text(source.get("likes", "")),
        "comments": _normalize_int_text(source.get("comments", "")),
        "favorites": _normalize_int_text(source.get("favorites", "")),
        "shares": _normalize_int_text(source.get("shares", "")),
        "followers": _normalize_int_text(source.get("followers", "")),
        "raw_video_path": "",
        "raw_audio_path": "",
        "txt_path": "",
        "download_status": "pending",
        "download_time": "",
        "asr_provider": "",
        "asr_model": "",
        "asr_time": "",
        "asr_status": "pending",
        "asr_char_count": "",
        "asr_chars_per_minute": "",
        "asr_quality_grade": "",
        "asr_quality_flags": "",
        "manual_reviewed": "no",
        "txt_sync_status": "pending",
        "dedup_status": "unknown",
        "dedup_group_id": "",
        "notes": _text(source, "notes") or "ingested from source links",
    }

    duration_seconds = _parse_duration_seconds(row["duration_text"])
    if duration_seconds is not None:
        row["duration_seconds"] = str(duration_seconds)

    return row


def merge_link_row(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    merged = dict(existing)
    for field in [
        "author",
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
    ]:
        incoming_value = (incoming.get(field, "") or "").strip()
        if incoming_value and not (merged.get(field, "") or "").strip():
            merged[field] = incoming_value

    incoming_notes = (incoming.get("notes", "") or "").strip()
    existing_notes = (merged.get("notes", "") or "").strip()
    if incoming_notes and incoming_notes not in existing_notes:
        merged["notes"] = f"{existing_notes} | {incoming_notes}".strip(" |")
    return merged


def load_link_sources(path: Path) -> list[dict[str, str]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Input file has no header: {path}")
        missing = [field for field in REQUIRED_SOURCE_FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"Input file missing required columns: {missing}")
        return [
            {key: "" if value is None else str(value) for key, value in row.items()}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]


def _required_text(source: dict[str, str], field: str) -> str:
    value = _text(source, field)
    if not value:
        raise ValueError(f"Required field is empty: {field}")
    return value


def _text(source: dict[str, str], field: str) -> str:
    return (source.get(field, "") or "").strip()


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
