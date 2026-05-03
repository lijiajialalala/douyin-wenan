from __future__ import annotations

import re
from dataclasses import dataclass


HTTP_ERROR_PATTERN = re.compile(r"\b(\d{3}) (?:Client|Server) Error\b", re.IGNORECASE)

RETRYABLE = "retryable"
BLOCKED = "blocked"
TERMINAL = "terminal"


@dataclass(frozen=True)
class FailureInfo:
    failure_class: str
    failure_code: str


def hydrate_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], bool]:
    hydrated: list[dict[str, str]] = []
    changed = False
    for row in rows:
        row_copy = dict(row)
        changed = hydrate_failure_metadata(row_copy) or changed
        hydrated.append(row_copy)
    return hydrated, changed


def hydrate_failure_metadata(row: dict[str, str]) -> bool:
    changed = False

    if (row.get("download_status", "") or "").strip() == "failed" and not (row.get("download_failure_class", "") or "").strip():
        message = _extract_latest_failure_message((row.get("notes", "") or ""), prefix="download failed:")
        if message:
            decision = classify_download_failure(message)
            row["download_failure_class"] = decision.failure_class
            row["download_failure_code"] = decision.failure_code
            if not (row.get("download_failure_count", "") or "").strip():
                row["download_failure_count"] = "1"
            changed = True

    if (row.get("asr_status", "") or "").strip() == "failed" and not (row.get("asr_failure_class", "") or "").strip():
        message = _extract_latest_failure_message((row.get("notes", "") or ""), prefix="asr failed:")
        if message:
            decision = classify_asr_failure(message)
            row["asr_failure_class"] = decision.failure_class
            row["asr_failure_code"] = decision.failure_code
            if not (row.get("asr_failure_count", "") or "").strip():
                row["asr_failure_count"] = "1"
            changed = True

    return changed


def classify_download_failure(error: BaseException | str) -> FailureInfo:
    message = _normalize_message(error)
    http_code = _extract_http_code(message)
    if http_code in {500, 502, 503, 504}:
        return FailureInfo(RETRYABLE, f"http_{http_code}")
    if http_code == 404:
        return FailureInfo(TERMINAL, "http_404")
    if http_code == 403:
        return FailureInfo(BLOCKED, "http_403")
    if http_code == 429:
        return FailureInfo(BLOCKED, "http_429")
    if _looks_like_timeout(message):
        return FailureInfo(RETRYABLE, "network_timeout")
    if _looks_like_connection_error(message):
        return FailureInfo(RETRYABLE, "network_connection")
    if "unable to extract douyin video id" in message:
        return FailureInfo(TERMINAL, "invalid_video_link")
    if "unable to locate play_addr" in message:
        return FailureInfo(BLOCKED, "share_page_parse")
    if "unexpected media content-type" in message:
        return FailureInfo(BLOCKED, "unexpected_content_type")
    if "downloaded file is empty" in message:
        return FailureInfo(RETRYABLE, "empty_download")
    return FailureInfo(BLOCKED, "download_unknown")


def classify_asr_failure(error: BaseException | str) -> FailureInfo:
    message = _normalize_message(error)
    http_code = _extract_http_code(message)
    if http_code in {500, 502, 503, 504}:
        return FailureInfo(RETRYABLE, f"http_{http_code}")
    if http_code == 429:
        return FailureInfo(BLOCKED, "http_429")
    if http_code == 403:
        return FailureInfo(BLOCKED, "http_403")
    if _looks_like_timeout(message):
        return FailureInfo(RETRYABLE, "network_timeout")
    if _looks_like_connection_error(message):
        return FailureInfo(RETRYABLE, "network_connection")
    if "missing required api key env" in message:
        return FailureInfo(BLOCKED, "missing_api_key")
    if "ffmpeg audio extraction failed" in message or "ffmpeg produced no audio output" in message:
        return FailureInfo(BLOCKED, "audio_extraction")
    if "did not contain text" in message:
        return FailureInfo(BLOCKED, "empty_transcript")
    return FailureInfo(BLOCKED, "asr_unknown")


def _extract_http_code(message: str) -> int | None:
    match = HTTP_ERROR_PATTERN.search(message)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _looks_like_timeout(message: str) -> bool:
    return any(
        token in message
        for token in [
            "timeout",
            "timed out",
            "readtimeout",
            "connecttimeout",
        ]
    )


def _looks_like_connection_error(message: str) -> bool:
    return any(
        token in message
        for token in [
            "connection aborted",
            "connection reset",
            "connection refused",
            "connectionerror",
            "temporarily unavailable",
            "remote disconnected",
        ]
    )


def _normalize_message(error: BaseException | str) -> str:
    if isinstance(error, BaseException):
        text = str(error)
    else:
        text = str(error)
    return text.strip().lower()


def _extract_latest_failure_message(notes: str, *, prefix: str) -> str:
    parts = [part.strip() for part in (notes or "").split("|") if part.strip()]
    lowered_prefix = prefix.lower()
    for part in reversed(parts):
        lowered = part.lower()
        if lowered.startswith(lowered_prefix):
            return part[len(prefix) :].strip()
    return ""
