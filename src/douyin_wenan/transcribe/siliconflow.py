from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass(frozen=True)
class SiliconFlowTranscription:
    text: str
    response_id: str


def require_api_key(env_name: str) -> str:
    value = os.getenv(env_name, "").strip()
    if not value:
        raise ValueError(f"Missing required API key env: {env_name}")
    return value


def transcribe_audio_file(*, audio_path: Path, api_key: str, base_url: str, model: str) -> SiliconFlowTranscription:
    endpoint = _build_api_url(base_url, "/v1/audio/transcriptions")
    headers = {"Authorization": f"Bearer {api_key}"}
    with audio_path.open("rb") as fh:
        files = {"file": (audio_path.name, fh, "audio/mpeg")}
        data = {"model": model}
        response = requests.post(endpoint, headers=headers, files=files, data=data, timeout=600)
    response.raise_for_status()
    payload = response.json()
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("SiliconFlow transcription response did not contain text")
    return SiliconFlowTranscription(text=text, response_id=str(payload.get("id", "")))


def _build_api_url(base_url: str, path: str) -> str:
    base = (base_url or "").rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    if base.endswith("/v1") and suffix.startswith("/v1/"):
        return base + suffix[len("/v1") :]
    return base + suffix
