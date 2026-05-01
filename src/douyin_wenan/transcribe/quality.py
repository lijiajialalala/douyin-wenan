from __future__ import annotations

from douyin_wenan.common.text_io import compact_char_count


def grade_transcript(text: str, duration_seconds: str) -> tuple[str, str, int, str]:
    char_count = compact_char_count(text)
    flags: list[str] = []
    cpm_text = ""

    seconds_value = 0
    if (duration_seconds or "").strip().isdigit():
        seconds_value = int(duration_seconds)
    if seconds_value > 0 and char_count > 0:
        minutes = seconds_value / 60
        cpm = char_count / minutes
        cpm_text = f"{cpm:.2f}"
        if cpm < 80:
            flags.append("low_density")
        elif cpm > 900:
            flags.append("high_density")

    if char_count == 0:
        flags.append("empty_transcript")
        grade = "D"
    elif char_count < 50:
        flags.append("short_transcript")
        grade = "C"
    elif "low_density" in flags or "high_density" in flags:
        grade = "C"
    else:
        grade = "B"

    return grade, ",".join(flags), char_count, cpm_text
