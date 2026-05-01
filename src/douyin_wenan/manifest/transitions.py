from __future__ import annotations

from douyin_wenan.common.time_utils import current_timestamp_text


DOWNLOAD_ALLOWED = {
    "pending": {"ok", "failed"},
    "failed": {"pending"},
    "ok": set(),
}

ASR_ALLOWED = {
    "pending": {"ok", "failed"},
    "failed": {"pending"},
    "ok": set(),
}

TXT_SYNC_ALLOWED = {
    "pending": {"ok", "failed"},
    "failed": {"pending"},
    "ok": set(),
}

DEDUP_ALLOWED = {
    "unknown": {"unique", "near_duplicate", "duplicate"},
    "unique": {"near_duplicate"},
    "near_duplicate": {"unique"},
    "duplicate": set(),
}


def transition_download(row: dict[str, str], new_status: str) -> dict[str, str]:
    _transition(row, "download_status", DOWNLOAD_ALLOWED, new_status)
    return row


def transition_asr(row: dict[str, str], new_status: str) -> dict[str, str]:
    if new_status == "ok" and row.get("download_status") != "ok":
        raise ValueError("Cannot mark ASR ok unless download_status is ok")
    _transition(row, "asr_status", ASR_ALLOWED, new_status)
    return row


def transition_txt_sync(row: dict[str, str], new_status: str) -> dict[str, str]:
    if new_status == "ok":
        if row.get("asr_status") != "ok":
            raise ValueError("Cannot mark txt sync ok unless asr_status is ok")
        if not (row.get("txt_path", "") or "").strip():
            raise ValueError("Cannot mark txt sync ok without txt_path")
    _transition(row, "txt_sync_status", TXT_SYNC_ALLOWED, new_status)
    return row


def transition_dedup(row: dict[str, str], new_status: str) -> dict[str, str]:
    if new_status != "unknown":
        if row.get("txt_sync_status") != "ok":
            raise ValueError("Cannot classify dedup unless txt_sync_status is ok")
        if not (row.get("txt_path", "") or "").strip():
            raise ValueError("Cannot classify dedup without txt_path")
    _transition(row, "dedup_status", DEDUP_ALLOWED, new_status)
    return row


def reset_download(row: dict[str, str], reason: str | None = None) -> dict[str, str]:
    row["download_status"] = "pending"
    row["download_time"] = ""
    row["raw_video_path"] = ""
    row["raw_audio_path"] = ""
    reset_asr(row)
    if reason:
        _append_note(row, f"download reset: {reason}")
    return row


def reset_asr(row: dict[str, str], reason: str | None = None) -> dict[str, str]:
    row["asr_status"] = "pending"
    row["asr_provider"] = ""
    row["asr_model"] = ""
    row["asr_time"] = ""
    row["asr_text_path"] = ""
    row["asr_char_count"] = ""
    row["asr_chars_per_minute"] = ""
    row["asr_quality_grade"] = ""
    row["asr_quality_flags"] = ""
    reset_txt_sync(row)
    if reason:
        _append_note(row, f"asr reset: {reason}")
    return row


def reset_txt_sync(row: dict[str, str], reason: str | None = None) -> dict[str, str]:
    row["txt_sync_status"] = "pending"
    row["txt_path"] = ""
    reset_dedup(row)
    if reason:
        _append_note(row, f"txt sync reset: {reason}")
    return row


def reset_dedup(row: dict[str, str], reason: str | None = None) -> dict[str, str]:
    row["dedup_status"] = "unknown"
    row["dedup_group_id"] = ""
    if reason:
        _append_note(row, f"dedup reset: {reason}")
    return row


def mark_download_succeeded(row: dict[str, str], *, raw_video_path: str, note: str | None = None) -> dict[str, str]:
    row["raw_video_path"] = raw_video_path
    row["download_time"] = current_timestamp_text()
    transition_download(row, "ok")
    if note:
        _append_note(row, note)
    return row


def mark_download_failed(row: dict[str, str], *, reason: str) -> dict[str, str]:
    row["raw_video_path"] = ""
    transition_download(row, "failed")
    _append_note(row, f"download failed: {reason}")
    return row


def mark_asr_succeeded(
    row: dict[str, str],
    *,
    raw_audio_path: str,
    asr_text_path: str,
    asr_provider: str,
    asr_model: str,
    asr_char_count: int,
    asr_chars_per_minute: str,
    asr_quality_grade: str,
    asr_quality_flags: str,
    note: str | None = None,
) -> dict[str, str]:
    row["raw_audio_path"] = raw_audio_path
    row["asr_text_path"] = asr_text_path
    row["asr_provider"] = asr_provider
    row["asr_model"] = asr_model
    row["asr_time"] = current_timestamp_text()
    row["asr_char_count"] = str(asr_char_count)
    row["asr_chars_per_minute"] = asr_chars_per_minute
    row["asr_quality_grade"] = asr_quality_grade
    row["asr_quality_flags"] = asr_quality_flags
    transition_asr(row, "ok")
    if note:
        _append_note(row, note)
    return row


def mark_asr_failed(row: dict[str, str], *, reason: str) -> dict[str, str]:
    row["raw_audio_path"] = ""
    row["asr_text_path"] = ""
    transition_asr(row, "failed")
    _append_note(row, f"asr failed: {reason}")
    return row


def mark_txt_sync_succeeded(row: dict[str, str], *, txt_path: str, note: str | None = None) -> dict[str, str]:
    row["txt_path"] = txt_path
    transition_txt_sync(row, "ok")
    if note:
        _append_note(row, note)
    return row


def mark_txt_sync_failed(row: dict[str, str], *, reason: str) -> dict[str, str]:
    row["txt_path"] = ""
    transition_txt_sync(row, "failed")
    _append_note(row, f"txt sync failed: {reason}")
    return row


def mark_dedup_classification(
    row: dict[str, str],
    *,
    dedup_status: str,
    dedup_group_id: str,
    note: str | None = None,
) -> dict[str, str]:
    row["dedup_group_id"] = dedup_group_id
    transition_dedup(row, dedup_status)
    if note:
        _append_note(row, note)
    return row


def _transition(
    row: dict[str, str],
    field: str,
    allowed_map: dict[str, set[str]],
    new_status: str,
) -> None:
    current = (row.get(field, "") or "").strip()
    if current == new_status:
        return
    allowed = allowed_map.get(current, set())
    if new_status not in allowed:
        raise ValueError(f"Illegal transition for {field}: {current!r} -> {new_status!r}")
    row[field] = new_status


def _append_note(row: dict[str, str], message: str) -> None:
    existing = (row.get("notes", "") or "").strip()
    row["notes"] = f"{existing} | {message}".strip(" |")
