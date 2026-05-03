from __future__ import annotations

import codecs
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

from douyin_wenan.common.ids import extract_video_id
from douyin_wenan.paths import ensure_parent_dir


MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)
PLAY_ADDR_PATTERN = re.compile(r'"play_addr":\{"uri":"[^"]+","url_list":\["([^"]+)"')
CHUNK_SIZE = 1024 * 1024
DEFAULT_DOWNLOAD_ATTEMPTS = 3


@dataclass(frozen=True)
class DownloadResult:
    work_id: str
    output_path: Path
    bytes_written: int
    share_page_url: str
    media_url: str


def download_douyin_video(
    *,
    video_link: str,
    work_id: str,
    author: str,
    raw_video_dir: Path,
    max_attempts: int = DEFAULT_DOWNLOAD_ATTEMPTS,
) -> DownloadResult:
    video_id = extract_video_id(video_link)
    if not video_id:
        raise ValueError(f"Unable to extract Douyin video id from link: {video_link}")

    share_page_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": MOBILE_USER_AGENT,
            "Referer": "https://www.iesdouyin.com/",
        }
    )
    media_url = resolve_media_url(session, share_page_url)
    output_path = build_output_path(raw_video_dir=raw_video_dir, author=author, work_id=work_id)

    if output_path.exists() and output_path.stat().st_size > 0:
        return DownloadResult(
            work_id=work_id,
            output_path=output_path,
            bytes_written=output_path.stat().st_size,
            share_page_url=share_page_url,
            media_url="",
        )

    ensure_parent_dir(output_path)
    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    if temp_path.exists():
        temp_path.unlink()

    attempts = max(1, int(max_attempts))
    errors: list[str] = []
    last_media_url = ""
    for attempt_index in range(attempts):
        try:
            media_urls = resolve_media_urls(session, share_page_url)
        except Exception as exc:
            errors.append(f"attempt {attempt_index + 1}: share page resolve failed: {exc}")
            continue

        for media_url in media_urls:
            last_media_url = media_url
            try:
                bytes_written = _download_media_url(
                    session=session,
                    media_url=media_url,
                    share_page_url=share_page_url,
                    temp_path=temp_path,
                )
                temp_path.replace(output_path)
                return DownloadResult(
                    work_id=work_id,
                    output_path=output_path,
                    bytes_written=bytes_written,
                    share_page_url=share_page_url,
                    media_url=media_url,
                )
            except Exception as exc:
                if temp_path.exists():
                    temp_path.unlink()
                errors.append(f"attempt {attempt_index + 1}: {media_url} -> {exc}")

    raise ValueError(_summarize_download_errors(errors, fallback_media_url=last_media_url))


def resolve_media_url(session: requests.Session, share_page_url: str) -> str:
    response = session.get(share_page_url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return extract_play_addr_url(response.text)


def resolve_media_urls(session: requests.Session, share_page_url: str) -> list[str]:
    return build_candidate_media_urls(resolve_media_url(session, share_page_url))


def extract_play_addr_url(html: str) -> str:
    match = PLAY_ADDR_PATTERN.search(html)
    if not match:
        raise ValueError("Unable to locate play_addr url in share page html")
    return codecs.decode(match.group(1), "unicode_escape")


def build_candidate_media_urls(media_url: str) -> list[str]:
    candidates: list[str] = []
    if "/playwm/" in media_url:
        candidates.append(media_url.replace("/playwm/", "/play/"))
    candidates.append(media_url)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _download_media_url(
    *,
    session: requests.Session,
    media_url: str,
    share_page_url: str,
    temp_path: Path,
) -> int:
    response = session.get(
        media_url,
        headers={"Referer": share_page_url},
        stream=True,
        timeout=120,
        allow_redirects=True,
    )
    response.raise_for_status()
    content_type = (response.headers.get("content-type", "") or "").lower()
    if "video" not in content_type and "octet-stream" not in content_type:
        response.close()
        raise ValueError(f"Unexpected media content-type: {content_type or 'missing'}")

    bytes_written = 0
    try:
        with temp_path.open("wb") as fh:
            for chunk in response.iter_content(CHUNK_SIZE):
                if not chunk:
                    continue
                fh.write(chunk)
                bytes_written += len(chunk)
    finally:
        response.close()

    if bytes_written <= 0:
        raise ValueError("Downloaded file is empty")
    return bytes_written


def _summarize_download_errors(errors: Iterable[str], *, fallback_media_url: str) -> str:
    unique_errors: list[str] = []
    seen: set[str] = set()
    for error in errors:
        normalized = error.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_errors.append(normalized)
    if not unique_errors:
        if fallback_media_url:
            return f"download failed for media url: {fallback_media_url}"
        return "download failed with no recoverable media candidate"
    preview = " | ".join(unique_errors[:4])
    if len(unique_errors) > 4:
        preview += f" | ... ({len(unique_errors)} errors total)"
    return preview


def build_output_path(*, raw_video_dir: Path, author: str, work_id: str) -> Path:
    return raw_video_dir / author / f"{work_id}.mp4"
