from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from douyin_wenan.paths import ensure_parent_dir

from .cleaning import clean_transcript_text
from .openai_correction import OpenAICorrectionResult


@dataclass(frozen=True)
class TranscriptArtifactPaths:
    raw_text_path: Path
    final_text_path: Path
    correction_json_path: Path


@dataclass(frozen=True)
class TranscriptProcessResult:
    final_text: str
    correction_applied: bool
    correction_json_path: str
    note: str


def build_transcript_artifact_paths(*, asr_text_dir: Path, author: str, work_id: str) -> TranscriptArtifactPaths:
    author_dir = asr_text_dir / author
    return TranscriptArtifactPaths(
        raw_text_path=author_dir / f"{work_id}.raw.txt",
        final_text_path=author_dir / f"{work_id}.txt",
        correction_json_path=author_dir / f"{work_id}.correction.json",
    )


def process_transcript_text(
    *,
    raw_text: str,
    raw_text_path: Path,
    final_text_path: Path,
    correction_json_path: Path | None,
    correction_runner: Callable[[str], OpenAICorrectionResult] | None,
) -> TranscriptProcessResult:
    ensure_parent_dir(raw_text_path)
    raw_text_path.write_text(raw_text or "", encoding="utf-8")

    normalized_text = clean_transcript_text(raw_text)
    if not normalized_text:
        raise ValueError("Safe-normalized transcript is empty")

    final_text = normalized_text
    correction_applied = False
    note = "safe normalized only"
    correction_json_value = ""

    if correction_runner is not None and correction_json_path is not None:
        try:
            correction_result = correction_runner(normalized_text)
            final_text = correction_result.final_text.strip()
            if not final_text:
                raise ValueError("OpenAI correction returned empty final_text")
            _write_correction_audit(
                correction_json_path=correction_json_path,
                payload={
                    "status": "ok",
                    "input_text": normalized_text,
                    "final_text": final_text,
                    "edits": correction_result.edits,
                    "needs_review": correction_result.needs_review,
                    "raw_response_text": correction_result.raw_response_text,
                },
            )
            correction_json_value = str(correction_json_path.resolve())
            correction_applied = True
            note = f"openai correction ok edits={len(correction_result.edits)}"
            if correction_result.needs_review:
                note += " needs_review"
        except Exception as exc:
            candidate_payload = _candidate_payload_from_exception(exc)
            _write_correction_audit(
                correction_json_path=correction_json_path,
                payload=_drop_empty(
                    {
                    "status": "fallback",
                    "input_text": normalized_text,
                    "final_text": normalized_text,
                    "error": str(exc),
                    "candidate": candidate_payload,
                    }
                ),
            )
            correction_json_value = str(correction_json_path.resolve())
            note = f"openai correction fallback: {exc}"

    ensure_parent_dir(final_text_path)
    final_text_path.write_text(final_text, encoding="utf-8")
    return TranscriptProcessResult(
        final_text=final_text,
        correction_applied=correction_applied,
        correction_json_path=correction_json_value,
        note=note,
    )


def _write_correction_audit(*, correction_json_path: Path, payload: dict[str, object]) -> None:
    ensure_parent_dir(correction_json_path)
    correction_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _candidate_payload_from_exception(exc: Exception) -> dict[str, object] | None:
    final_text = str(getattr(exc, "candidate_final_text", "") or "").strip()
    edits = getattr(exc, "candidate_edits", None)
    needs_review = getattr(exc, "candidate_needs_review", None)
    raw_response_text = str(getattr(exc, "raw_response_text", "") or "").strip()

    payload: dict[str, object] = {}
    if final_text:
        payload["final_text"] = final_text
    if isinstance(edits, list) and edits:
        payload["edits"] = edits
    if isinstance(needs_review, bool):
        payload["needs_review"] = needs_review
    if raw_response_text:
        payload["raw_response_text"] = raw_response_text
    return payload or None


def _drop_empty(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in payload.items()
        if value not in ("", None, []) and not (isinstance(value, dict) and not value)
    }
