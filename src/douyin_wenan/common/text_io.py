from __future__ import annotations

import re
from pathlib import Path


TEXT_FIELDS = [
    "标题",
    "作者",
    "作品ID",
    "粉丝数",
    "平台",
    "账号链接",
    "视频链接",
    "发布时间",
    "时长",
    "点赞",
    "评论",
    "收藏",
    "转发",
    "类型",
    "文案字数",
    "疑问句数",
    "原始文件",
    "整理状态",
    "ASR来源",
    "ASR质量等级",
    "是否人工校对",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def split_transcript_document(text: str) -> tuple[str, str]:
    marker = "正文文案："
    if marker not in text:
        return text, ""
    head, body = text.split(marker, 1)
    return head, body.strip()


def parse_transcript_header(path: Path) -> tuple[dict[str, str], str]:
    text = read_text(path)
    head, body = split_transcript_document(text)
    meta: dict[str, str] = {}
    for raw_line in head.splitlines():
        line = raw_line.strip()
        if not line or "：" not in line:
            continue
        key, value = line.split("：", 1)
        key = key.strip()
        value = value.strip()
        if key in TEXT_FIELDS:
            meta[key] = value
    return meta, body


def compact_char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def count_question_marks(text: str) -> int:
    content = text or ""
    return content.count("?") + content.count("？")
