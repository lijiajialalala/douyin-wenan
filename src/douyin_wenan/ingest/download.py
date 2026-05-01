from __future__ import annotations

import codecs
import re
from dataclasses import dataclass
from pathlib import Path

import requests

from douyin_wenan.common.ids import extract_video_id
from douyin_wenan.paths import ensure_parent_dir


MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)
PLAY_ADDR_PATTERN = re.compile(r'"play_addr":\{"uri":"[^"]+","url_list":\["([^"]+)"')
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class DownloadResult:
    work_id: str
    output_path: Path
    bytes_written: int
    share_page_url: str
    media_url: str


def download_douyin_video(*, video_link: str, work_id: str, author: str, raw_video_dir: Path) -> DownloadResult:
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
            media_url=media_url,
        )

    ensure_parent_dir(output_path)
    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    if temp_path.exists():
        temp_path.unlink()

    response = session.get(media_url, stream=True, timeout=120, allow_redirects=True)
    response.raise_for_status()
    content_type = (response.headers.get("content-type", "") or "").lower()
    if "video" not in content_type and "octet-stream" not in content_type:
        raise ValueError(f"Unexpected media content-type: {content_type or 'missing'}")

    bytes_written = 0
    try:
        with temp_path.open("wb") as fh:
            for chunk in response.iter_content(CHUNK_SIZE):
                if not chunk:
                    continue
                fh.write(chunk)
                bytes_written += len(chunk)
        if bytes_written <= 0:
            raise ValueError("Downloaded file is empty")
        temp_path.replace(output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    finally:
        response.close()

    return DownloadResult(
        work_id=work_id,
        output_path=output_path,
        bytes_written=bytes_written,
        share_page_url=share_page_url,
        media_url=media_url,
    )


def resolve_media_url(session: requests.Session, share_page_url: str) -> str:
    response = session.get(share_page_url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return extract_play_addr_url(response.text)


def extract_play_addr_url(html: str) -> str:
    match = PLAY_ADDR_PATTERN.search(html)
    if not match:
        raise ValueError("Unable to locate play_addr url in share page html")
    return codecs.decode(match.group(1), "unicode_escape")


def build_output_path(*, raw_video_dir: Path, author: str, work_id: str) -> Path:
    return raw_video_dir / author / f"{work_id}.mp4"
