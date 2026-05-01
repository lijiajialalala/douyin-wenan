from __future__ import annotations

import re


MUSIC_MARKERS = ("🎼", "🎵", "🎶", "♪", "♫", "♬", "♩")
NOISE_TAG_PATTERN = re.compile(
    r"[\[【（(＜<《]?\s*(音乐|bgm|音效|掌声|鼓掌|笑声|哭声|杂音|噪音|转场|片头|片尾|旁白)\s*[\]】）)＞>》]?",
    re.IGNORECASE,
)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)
SPACE_BEFORE_PUNCT = re.compile(r"\s+([，。！？；：、,.!?;:])")
MULTI_SPACE = re.compile(r"[ \t]+")
MULTI_NEWLINE = re.compile(r"\n{3,}")
COMMON_REPLACEMENTS = (
    ("阿尔蒙", "阿尔芒"),
    ("老鸭芒", "老亚芒"),
    ("老鸭毛", "老亚芒"),
    ("科血", "咳血"),
    ("烦咬", "反咬"),
    ("名利厂里", "名利场里"),
    ("名利厂理", "名利场里"),
    ("网袋", "网贷"),
    ("债务血球", "债务雪球"),
    ("扒的最壁朝天", "扒得最底朝天"),
    ("二芒", "阿尔芒"),
    ("肺结和晚期", "肺结核晚期"),
    ("庄富不会让你真负", "装富不会让你真富"),
)


def clean_transcript_text(text: str) -> str:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    for marker in MUSIC_MARKERS:
        cleaned = cleaned.replace(marker, " ")
    cleaned = NOISE_TAG_PATTERN.sub(" ", cleaned)
    cleaned = EMOJI_PATTERN.sub(" ", cleaned)

    for source, target in COMMON_REPLACEMENTS:
        cleaned = cleaned.replace(source, target)

    cleaned = SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)
    cleaned = MULTI_SPACE.sub(" ", cleaned)
    cleaned = MULTI_NEWLINE.sub("\n\n", cleaned)
    cleaned = "\n".join(line.strip() for line in cleaned.split("\n"))
    cleaned = cleaned.strip()

    if cleaned.endswith("抖音。") and len(cleaned) > 20:
        cleaned = cleaned[: -len("抖音。")].rstrip()
    elif cleaned.endswith("抖音") and len(cleaned) > 20:
        cleaned = cleaned[: -len("抖音")].rstrip()

    return cleaned
