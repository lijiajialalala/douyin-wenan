from __future__ import annotations

import json
import os
from dataclasses import dataclass
from math import ceil

import requests
from requests import Response

from douyin_wenan.common.text_io import compact_char_count


SYSTEM_PROMPT = """你是短视频ASR转写校对员。
只允许修正明显错词、同音误识别、断词错误、明显标点错误。
禁止总结、润色、扩写、压缩、改写风格、补充不存在的信息。
保留原始口语节奏、语气和信息顺序。
只输出一个JSON对象，不要输出Markdown代码块，不要附加解释。"""


@dataclass(frozen=True)
class OpenAICorrectionResult:
    final_text: str
    edits: list[dict[str, object]]
    needs_review: bool
    raw_response_text: str


class OpenAICorrectionRejected(ValueError):
    def __init__(
        self,
        message: str,
        *,
        candidate_final_text: str,
        candidate_edits: list[dict[str, object]],
        candidate_needs_review: bool,
        raw_response_text: str,
    ) -> None:
        super().__init__(message)
        self.candidate_final_text = candidate_final_text
        self.candidate_edits = candidate_edits
        self.candidate_needs_review = candidate_needs_review
        self.raw_response_text = raw_response_text


def require_api_key(env_name: str) -> str:
    value = os.getenv(env_name, "").strip()
    if not value:
        raise ValueError(f"Missing required API key env: {env_name}")
    return value


def correct_transcript_text(
    *,
    transcript_text: str,
    api_key: str,
    base_url: str,
    model: str,
    max_char_delta_ratio: float = 0.08,
    max_edit_count: int = 40,
    max_edit_density_per_1000_chars: float = 6.0,
) -> OpenAICorrectionResult:
    endpoint = build_api_url(base_url, "/v1/chat/completions")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "请校对下面的ASR转写，只修正明显错误，输出JSON对象，字段为 "
                    "final_text, edits, needs_review。\n\n"
                    f"原始转写：\n{transcript_text}"
                ),
            },
        ],
    }
    response = requests.post(endpoint, headers=headers, json=payload, timeout=600)
    response.raise_for_status()
    response_payload = _load_json_response(response)
    content = _extract_message_content(response_payload)
    parsed = _parse_json_payload(content)
    final_text = str(parsed.get("final_text", "")).strip()
    if not final_text:
        raise ValueError("OpenAI correction response did not contain final_text")
    edits = parsed.get("edits", [])
    if not isinstance(edits, list):
        raise ValueError("OpenAI correction response edits must be a list")
    normalized_edits = [edit if isinstance(edit, dict) else {"value": edit} for edit in edits]
    allowed_edit_count = _max_allowed_edit_count(
        original_text=transcript_text,
        base_max_edit_count=max_edit_count,
        max_edit_density_per_1000_chars=max_edit_density_per_1000_chars,
    )
    if len(normalized_edits) > allowed_edit_count:
        raise OpenAICorrectionRejected(
            f"OpenAI correction returned too many edits: {len(normalized_edits)} > allowed {allowed_edit_count}",
            candidate_final_text=final_text,
            candidate_edits=normalized_edits,
            candidate_needs_review=bool(parsed.get("needs_review", False)),
            raw_response_text=content,
        )
    _validate_char_delta(
        original_text=transcript_text,
        final_text=final_text,
        max_char_delta_ratio=max_char_delta_ratio,
        edits=normalized_edits,
        needs_review=bool(parsed.get("needs_review", False)),
        raw_response_text=content,
    )
    return OpenAICorrectionResult(
        final_text=final_text,
        edits=normalized_edits,
        needs_review=bool(parsed.get("needs_review", False)),
        raw_response_text=content,
    )


def build_api_url(base_url: str, path: str) -> str:
    base = (base_url or "").rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    if base.endswith("/v1") and suffix.startswith("/v1/"):
        return base + suffix[len("/v1") :]
    return base + suffix


def _load_json_response(response: Response) -> dict[str, object]:
    try:
        decoded = response.content.decode("utf-8")
        payload = json.loads(decoded)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OpenAI correction response root must be an object")
    return payload


def _extract_message_content(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI correction response did not contain choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ValueError("OpenAI correction response did not contain message")
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    parts.append(str(text))
        joined = "".join(parts).strip()
        if joined:
            return joined
    raise ValueError("OpenAI correction response did not contain textual content")


def _parse_json_payload(content: str) -> dict[str, object]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = _strip_code_fence(stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("OpenAI correction response was not valid JSON")
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI correction response root must be an object")
    return parsed


def _strip_code_fence(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return text


def _validate_char_delta(
    *,
    original_text: str,
    final_text: str,
    max_char_delta_ratio: float,
    edits: list[dict[str, object]],
    needs_review: bool,
    raw_response_text: str,
) -> None:
    original_count = compact_char_count(original_text)
    final_count = compact_char_count(final_text)
    if original_count <= 0:
        return
    delta_ratio = abs(final_count - original_count) / original_count
    if delta_ratio > max(0.0, max_char_delta_ratio):
        raise OpenAICorrectionRejected(
            (
                "OpenAI correction changed transcript length too much: "
                f"original={original_count} final={final_count}"
            ),
            candidate_final_text=final_text,
            candidate_edits=edits,
            candidate_needs_review=needs_review,
            raw_response_text=raw_response_text,
        )


def _max_allowed_edit_count(
    *,
    original_text: str,
    base_max_edit_count: int,
    max_edit_density_per_1000_chars: float,
) -> int:
    base_limit = max(1, int(base_max_edit_count))
    char_count = compact_char_count(original_text)
    if char_count <= 0:
        return base_limit
    density_limit = ceil(max(0.0, max_edit_density_per_1000_chars) * char_count / 1000)
    return max(base_limit, density_limit)
