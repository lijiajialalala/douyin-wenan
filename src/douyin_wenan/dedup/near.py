from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher


NORMALIZE_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class DedupDecision:
    status: str
    group_id: str
    similarity: float
    matched_work_id: str


def classify_against_existing(
    *,
    work_id: str,
    text: str,
    existing_items: list[tuple[str, str]],
    near_threshold: float = 0.97,
) -> DedupDecision:
    normalized_text = normalize_text(text)
    if not normalized_text:
        return DedupDecision(status="unique", group_id="", similarity=0.0, matched_work_id="")

    text_hash = stable_text_hash(normalized_text)
    best_match_id = ""
    best_similarity = 0.0
    for other_work_id, other_text in existing_items:
        if other_work_id == work_id:
            continue
        normalized_other = normalize_text(other_text)
        if not normalized_other:
            continue
        if stable_text_hash(normalized_other) == text_hash:
            return DedupDecision(
                status="duplicate",
                group_id=f"dup-{other_work_id}",
                similarity=1.0,
                matched_work_id=other_work_id,
            )

        similarity = SequenceMatcher(a=normalized_text, b=normalized_other).ratio()
        if similarity > best_similarity:
            best_similarity = similarity
            best_match_id = other_work_id

    if best_match_id and best_similarity >= near_threshold:
        return DedupDecision(
            status="near_duplicate",
            group_id=f"near-{best_match_id}",
            similarity=best_similarity,
            matched_work_id=best_match_id,
        )

    return DedupDecision(status="unique", group_id="", similarity=best_similarity, matched_work_id=best_match_id)


def normalize_text(text: str) -> str:
    return NORMALIZE_WS.sub("", (text or "").strip())


def stable_text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()
