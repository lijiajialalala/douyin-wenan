from __future__ import annotations

import re
from pathlib import Path

from douyin_wenan.common.text_io import compact_char_count, count_question_marks
from douyin_wenan.paths import ensure_parent_dir


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')
WHITESPACE_PATTERN = re.compile(r"\s+")
PUNCT_FOR_FILENAME = re.compile(r"[：:？?！!。，“”\"'、，；;（）()【】《》·]+")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?])")
CANONICAL_TITLE_LIMIT = 16


def build_standard_txt_path(*, corpus_root: Path, author: str, work_id: str, title: str, existing_txt_path: str) -> Path:
    existing = (existing_txt_path or "").strip()
    if existing:
        existing_path = Path(existing)
        if is_runtime_transcript_path(existing_path, corpus_root=corpus_root):
            return existing_path

    safe_title = sanitize_title_for_filename(title)
    filename = f"{work_id}_{safe_title}.txt"
    return corpus_root / author / "transcripts" / filename


def render_standard_transcript(row: dict[str, str], transcript_text: str) -> str:
    body = (transcript_text or "").strip()
    formatted_body = format_transcript_body(body)
    char_count = compact_char_count(body)
    question_count = count_question_marks(body)
    lines = [
        f"标题：{row.get('title', '')}",
        f"作者：{row.get('author', '')}",
        f"作品ID：{row.get('work_id', '')}",
        f"粉丝数：{row.get('followers', '')}",
        "平台：抖音",
        f"账号链接：{row.get('account_link', '')}",
        f"视频链接：{row.get('video_link', '')}",
        f"发布时间：{row.get('publish_time', '')}",
        f"时长：{row.get('duration_text', '')}",
        f"点赞：{row.get('likes', '')}",
        f"评论：{row.get('comments', '')}",
        f"收藏：{row.get('favorites', '')}",
        f"转发：{row.get('shares', '')}",
        "类型：待判断",
        f"文案字数：{char_count}",
        f"疑问句数：{question_count}",
        f"原始文件：{row.get('raw_video_path', '')}",
        "整理状态：ASR自动生成并清洗噪声，待人工校对",
        f"ASR来源：{build_asr_source_text(row)}",
        f"ASR质量等级：{row.get('asr_quality_grade', '')}",
        f"是否人工校对：{'是' if (row.get('manual_reviewed', '') or '').strip() == 'yes' else '否'}",
        "",
        "正文总结：",
        "一句话概括：",
        "核心问题：",
        "核心观点：",
        "结构骨架：",
        "可借鉴点：",
        "风险提醒：",
        "",
        "正文文案：",
        formatted_body,
        "",
    ]
    return "\n".join(lines)


def write_standard_transcript(*, output_path: Path, content: str) -> Path:
    ensure_parent_dir(output_path)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def sanitize_title_for_filename(title: str) -> str:
    text = primary_title_segment(title)
    text = INVALID_FILENAME_CHARS.sub(" ", text)
    text = PUNCT_FOR_FILENAME.sub(" ", text)
    text = WHITESPACE_PATTERN.sub("", text).strip()
    if not text:
        return "untitled"
    return text[:CANONICAL_TITLE_LIMIT]


def primary_title_segment(title: str) -> str:
    text = (title or "").replace("#", " ").strip()
    text = WHITESPACE_PATTERN.sub(" ", text)
    for splitter in ["：", ":", "？", "?", "！", "!", "。"]:
        if splitter in text:
            head = text.split(splitter, 1)[0].strip()
            if head:
                return head
    return text


def is_runtime_transcript_path(path: Path, *, corpus_root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(corpus_root.resolve(strict=False))
    except ValueError:
        return False
    return path.suffix.lower() == ".txt"


def format_transcript_body(text: str, *, target_paragraph_chars: int = 180) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    paragraphs: list[str] = []
    for raw_block in normalized.split("\n\n"):
        block = WHITESPACE_PATTERN.sub(" ", raw_block.strip())
        if not block:
            continue
        paragraphs.extend(_wrap_sentence_block(block, target_paragraph_chars=target_paragraph_chars))

    return "\n".join(paragraphs)


def build_asr_source_text(row: dict[str, str]) -> str:
    provider = (row.get("asr_provider", "") or "").strip()
    model = (row.get("asr_model", "") or "").strip()
    if provider and model:
        return f"{provider}/{model}"
    return provider or model


def _wrap_sentence_block(text: str, *, target_paragraph_chars: int) -> list[str]:
    parts = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(text) if part.strip()]
    if not parts:
        return [text]

    paragraphs: list[str] = []
    current = ""
    for part in parts:
        if not current:
            current = part
            continue
        if len(current) + len(part) <= target_paragraph_chars:
            current += part
            continue
        paragraphs.append(current)
        current = part

    if current:
        paragraphs.append(current)
    return paragraphs
