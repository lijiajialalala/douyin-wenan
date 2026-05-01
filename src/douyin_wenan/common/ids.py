from __future__ import annotations

import hashlib
import re


VIDEO_ID_PATTERN = re.compile(r"/video/(\d+)")


def extract_video_id(video_link: str) -> str | None:
    match = VIDEO_ID_PATTERN.search((video_link or "").strip())
    if not match:
        return None
    return match.group(1)


def synthetic_work_id(author: str, publish_time: str, title: str, video_link: str) -> str:
    base = "|".join(
        [
            (author or "").strip(),
            (publish_time or "").strip(),
            (title or "").strip(),
            (video_link or "").strip(),
        ]
    )
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"synthetic-{digest}"
