from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import yaml

from douyin_wenan.analysis.artifact_schema import load_yaml_document
from douyin_wenan.paths import ensure_parent_dir


CLASS_RANK = {
    "guardrail": 0,
    "structure": 1,
    "objective": 2,
    "style": 3,
    "signature": 4,
    "general_default": 5,
}
HARDNESS_RANK = {
    "required": 0,
    "preferred": 1,
    "optional": 2,
}
STATUS_RANK = {
    "active": 0,
    "validated": 1,
    "candidate": 2,
}


@dataclass(frozen=True)
class CompositionRequest:
    domain: str
    format: str
    goal: str
    content_type: str
    style_family: str = ""
    author_signature: str = ""
    author_scope: str = ""
    allow_candidate: bool = True


def load_skill_cards(skill_dir: Path) -> list[dict[str, object]]:
    return _load_card_dir(skill_dir)


def load_anti_skill_cards(anti_skill_dir: Path) -> list[dict[str, object]]:
    return _load_card_dir(anti_skill_dir)


def compose_plan(
    skill_cards: list[dict[str, object]],
    anti_skill_cards: list[dict[str, object]],
    request: CompositionRequest,
) -> dict[str, object]:
    matched_guardrails = [card for card in anti_skill_cards if _matches_anti_skill(card, request)]
    matched_skills = [card for card in skill_cards if _matches_skill_card(card, request)]
    dropped_cards: set[str] = set()
    override_decisions: list[dict[str, str]] = []
    unresolved_conflicts: list[str] = []

    dependency_ready_cards: list[dict[str, object]] = []
    matched_ids = {_card_id(card) for card in matched_skills}
    for card in matched_skills:
        dependencies = _string_list(card.get("depends_on"))
        if dependencies and not set(dependencies).issubset(matched_ids):
            dropped_cards.add(_card_id(card))
            continue
        dependency_ready_cards.append(card)

    slot_ownership: dict[str, str] = {}
    selected_skill_ids: set[str] = set()
    by_slot = _group_cards_by_slot(dependency_ready_cards)
    for slot, slot_cards in by_slot.items():
        winner, slot_dropped, slot_overrides, slot_conflicts = _resolve_slot(slot, slot_cards)
        dropped_cards.update(slot_dropped)
        override_decisions.extend(slot_overrides)
        unresolved_conflicts.extend(slot_conflicts)
        if winner is None:
            continue
        winner_id = _card_id(winner)
        slot_ownership[slot] = winner_id
        selected_skill_ids.add(winner_id)

    selected_guardrail_ids = sorted(_card_id(card) for card in matched_guardrails)
    selected_cards = sorted({*selected_skill_ids, *selected_guardrail_ids})

    if unresolved_conflicts:
        status = "review_required"
    elif slot_ownership:
        status = "resolved"
    else:
        status = "rejected"
        unresolved_conflicts.append("No compatible skill cards matched the requested routing inputs.")

    plan = {
        "composition_id": _composition_id(request, selected_cards),
        "domain": request.domain,
        "format": request.format,
        "goal": request.goal,
        "content_type": request.content_type,
        "style_family": request.style_family,
        "author_signature": request.author_signature,
        "selected_cards": selected_cards,
        "dropped_cards": sorted(dropped_cards),
        "override_decisions": override_decisions,
        "slot_ownership": slot_ownership,
        "unresolved_conflicts": unresolved_conflicts,
        "status": status,
        "notes": _build_notes(matched_guardrails, unresolved_conflicts),
    }
    return _drop_empty_fields(plan)


def write_composition_plan(plan: dict[str, object], output_path: Path) -> Path:
    ensure_parent_dir(output_path)
    output_path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return output_path


def default_composition_plan_path(analysis_dir: Path, plan: dict[str, object]) -> Path:
    return analysis_dir / "compositions" / f"{plan['composition_id']}.yaml"


def _load_card_dir(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    cards: list[dict[str, object]] = []
    for file_path in sorted(path.glob("*.yaml")):
        payload = load_yaml_document(file_path)
        payload["_source_path"] = str(file_path)
        cards.append(payload)
    return cards


def _matches_skill_card(card: dict[str, object], request: CompositionRequest) -> bool:
    status = str(card.get("status", "")).strip()
    if status == "deprecated":
        return False
    if status == "candidate" and not request.allow_candidate:
        return False
    if not _matches_dimension(card.get("domains"), request.domain):
        return False
    if not _matches_dimension(card.get("formats"), request.format):
        return False
    if not _matches_dimension(card.get("goals"), request.goal):
        return False
    if not _matches_dimension(card.get("content_types"), request.content_type):
        return False
    if not _matches_optional_dimension(card.get("style_families"), request.style_family):
        return False
    if not _matches_author_scope(card, request):
        return False
    if not _matches_author_signature(card, request):
        return False
    return True


def _matches_anti_skill(card: dict[str, object], request: CompositionRequest) -> bool:
    status = str(card.get("status", "")).strip()
    if status == "deprecated":
        return False
    if status == "candidate" and not request.allow_candidate:
        return False
    if not _matches_dimension(card.get("domains"), request.domain):
        return False
    if not _matches_dimension(card.get("formats"), request.format):
        return False
    if not _matches_dimension(card.get("goals"), request.goal):
        return False
    if not _matches_dimension(card.get("content_types"), request.content_type):
        return False
    if not _matches_author_scope(card, request):
        return False
    return True


def _matches_dimension(raw_values: object, expected: str) -> bool:
    values = _string_list(raw_values)
    if not values:
        return True
    return expected in values


def _matches_optional_dimension(raw_values: object, expected: str) -> bool:
    values = _string_list(raw_values)
    if not values:
        return True
    if not expected:
        return False
    return expected in values


def _matches_author_signature(card: dict[str, object], request: CompositionRequest) -> bool:
    author_signatures = _string_list(card.get("author_signatures"))
    card_type = str(card.get("card_type", "")).strip()

    if author_signatures:
        if not request.author_signature:
            return False
        if request.author_signature not in author_signatures:
            return False

    if card_type == "signature_pattern" and not request.author_signature:
        return False
    return True


def _matches_author_scope(card: dict[str, object], request: CompositionRequest) -> bool:
    author_scope = str(card.get("author_scope", "")).strip()
    promotion_status = str(card.get("promotion_status", "")).strip()

    if promotion_status == "author_local" and not author_scope:
        return False
    if not author_scope:
        return True
    return bool(request.author_scope and request.author_scope == author_scope)


def _group_cards_by_slot(cards: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for card in cards:
        for slot in _string_list(card.get("slots")):
            grouped.setdefault(slot, []).append(card)
    return grouped


def _resolve_slot(
    slot: str,
    cards: list[dict[str, object]],
) -> tuple[dict[str, object] | None, set[str], list[dict[str, str]], list[str]]:
    dropped_cards: set[str] = set()
    override_decisions: list[dict[str, str]] = []
    unresolved_conflicts: list[str] = []
    if not cards:
        return None, dropped_cards, override_decisions, unresolved_conflicts

    ordered = sorted(cards, key=_resolution_sort_key)
    override_filtered, override_dropped, override_conflicts = _apply_explicit_overrides(slot, ordered)
    dropped_cards.update(override_dropped)
    override_decisions.extend(_build_override_decisions(slot, override_filtered, override_dropped, ordered))
    unresolved_conflicts.extend(override_conflicts)
    if override_conflicts:
        return None, dropped_cards, override_decisions, unresolved_conflicts
    if not override_filtered:
        unresolved_conflicts.append(
            f"Slot '{slot}' has no remaining candidates after explicit overrides."
        )
        return None, dropped_cards, override_decisions, unresolved_conflicts

    ordered = sorted(override_filtered, key=_resolution_sort_key)
    winner = ordered[0]
    winner_signature = _conflict_signature(winner)
    tied = [card for card in ordered if _conflict_signature(card) == winner_signature]
    if len(tied) > 1:
        unresolved_conflicts.append(
            f"Slot '{slot}' has equally strong required candidates: {', '.join(_card_id(card) for card in tied)}"
        )
        dropped_cards.update(_card_id(card) for card in tied)
        return None, dropped_cards, override_decisions, unresolved_conflicts

    for challenger in ordered[1:]:
        resolution = _resolve_pair(slot, winner, challenger)
        if resolution["decision"] == "unresolved":
            unresolved_conflicts.append(str(resolution["reason"]))
            dropped_cards.add(_card_id(winner))
            dropped_cards.add(_card_id(challenger))
            return None, dropped_cards, override_decisions, unresolved_conflicts
        loser = resolution["loser"]
        loser_id = _card_id(loser)
        dropped_cards.add(loser_id)
        override_decisions.append(
            {
                "slot": slot,
                "winner": _card_id(resolution["winner"]),
                "dropped": loser_id,
                "reason": str(resolution["reason"]),
            }
        )
        winner = resolution["winner"]
    return winner, dropped_cards, override_decisions, unresolved_conflicts


def _apply_explicit_overrides(
    slot: str,
    cards: list[dict[str, object]],
) -> tuple[list[dict[str, object]], set[str], list[str]]:
    by_id = {_card_id(card): card for card in cards}
    overridden_ids: set[str] = set()
    conflicts: list[str] = []

    for left, right in combinations(cards, 2):
        left_id = _card_id(left)
        right_id = _card_id(right)
        left_overrides_right = right_id in _string_list(left.get("overrides"))
        right_overrides_left = left_id in _string_list(right.get("overrides"))
        if left_overrides_right and right_overrides_left:
            conflicts.append(
                f"Slot '{slot}' has mutually overriding cards: {left_id} and {right_id}"
            )
            return [], set(), conflicts

    for card in cards:
        for target_id in _string_list(card.get("overrides")):
            if target_id in by_id and target_id != _card_id(card):
                overridden_ids.add(target_id)

    survivors = [card for card in cards if _card_id(card) not in overridden_ids]
    return survivors, overridden_ids, conflicts


def _build_override_decisions(
    slot: str,
    survivors: list[dict[str, object]],
    overridden_ids: set[str],
    cards: list[dict[str, object]],
) -> list[dict[str, str]]:
    if not overridden_ids:
        return []

    by_id = {_card_id(card): card for card in cards}
    survivor_ids = {_card_id(card) for card in survivors}
    decisions: list[dict[str, str]] = []

    for overridden_id in sorted(overridden_ids):
        overriders = [
            card
            for card in cards
            if overridden_id in _string_list(card.get("overrides")) and _card_id(card) in survivor_ids
        ]
        if not overriders:
            overriders = [
                card for card in cards if overridden_id in _string_list(card.get("overrides"))
            ]
        if not overriders:
            continue
        winner = sorted(overriders, key=_resolution_sort_key)[0]
        decisions.append(
            {
                "slot": slot,
                "winner": _card_id(winner),
                "dropped": overridden_id,
                "reason": f"{_card_id(winner)} explicitly overrides {overridden_id}",
            }
        )
    return decisions


def _resolve_pair(slot: str, incumbent: dict[str, object], challenger: dict[str, object]) -> dict[str, object]:
    incumbent_id = _card_id(incumbent)
    challenger_id = _card_id(challenger)

    if challenger_id in _string_list(incumbent.get("overrides")):
        return {
            "decision": "resolved",
            "winner": incumbent,
            "loser": challenger,
            "reason": f"{incumbent_id} explicitly overrides {challenger_id}",
        }
    if incumbent_id in _string_list(challenger.get("overrides")):
        return {
            "decision": "resolved",
            "winner": challenger,
            "loser": incumbent,
            "reason": f"{challenger_id} explicitly overrides {incumbent_id}",
        }

    if _cards_incompatible(incumbent, challenger):
        if _hardness(incumbent) == "required" and _hardness(challenger) == "required":
            return {
                "decision": "unresolved",
                "reason": (
                    f"Slot '{slot}' has incompatible required cards: "
                    f"{incumbent_id} and {challenger_id}"
                ),
            }
        stronger, weaker = _stronger_card(incumbent, challenger)
        return {
            "decision": "resolved",
            "winner": stronger,
            "loser": weaker,
            "reason": f"{_card_id(stronger)} is stronger than incompatible card {_card_id(weaker)}",
        }

    stronger, weaker = _stronger_card(incumbent, challenger)
    if stronger is None:
        return {
            "decision": "unresolved",
            "reason": f"Slot '{slot}' has unresolved tie between {incumbent_id} and {challenger_id}",
        }
    return {
        "decision": "resolved",
        "winner": stronger,
        "loser": weaker,
        "reason": f"{_card_id(stronger)} outranks {_card_id(weaker)} for slot ownership",
    }


def _stronger_card(
    left: dict[str, object],
    right: dict[str, object],
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    left_key = _conflict_signature(left)
    right_key = _conflict_signature(right)
    if left_key == right_key:
        return None, None
    if left_key < right_key:
        return left, right
    return right, left


def _resolution_sort_key(card: dict[str, object]) -> tuple[object, ...]:
    return (*_conflict_signature(card), _card_id(card))


def _conflict_signature(card: dict[str, object]) -> tuple[object, ...]:
    return (
        _class_rank(card),
        _hardness_rank(card),
        -_specificity_score(card),
        -_priority(card),
        _status_rank(card),
    )


def _class_rank(card: dict[str, object]) -> int:
    if str(card.get("card_type", "")).strip() == "signature_pattern" or str(card.get("layer", "")).strip() == "author_signature":
        return CLASS_RANK["signature"]
    if _string_list(card.get("style_families")) or str(card.get("layer", "")).strip() == "style_family":
        return CLASS_RANK["style"]
    if _string_list(card.get("formats")) or _string_list(card.get("content_types")):
        return CLASS_RANK["structure"]
    if _string_list(card.get("goals")):
        return CLASS_RANK["objective"]
    return CLASS_RANK["general_default"]


def _hardness_rank(card: dict[str, object]) -> int:
    return HARDNESS_RANK.get(_hardness(card), 9)


def _hardness(card: dict[str, object]) -> str:
    return str(card.get("hardness", "")).strip() or "optional"


def _specificity_score(card: dict[str, object]) -> int:
    if _string_list(card.get("author_signatures")) or str(card.get("layer", "")).strip() == "author_signature":
        return 4
    if _string_list(card.get("style_families")) or str(card.get("layer", "")).strip() == "style_family":
        return 3
    if _string_list(card.get("content_types")) or _string_list(card.get("formats")):
        return 2
    if _string_list(card.get("goals")):
        return 1
    return 0


def _priority(card: dict[str, object]) -> int:
    value = card.get("priority")
    return int(value) if isinstance(value, int) else 0


def _status_rank(card: dict[str, object]) -> int:
    status = str(card.get("status", "")).strip()
    return STATUS_RANK.get(status, 9)


def _cards_incompatible(left: dict[str, object], right: dict[str, object]) -> bool:
    left_id = _card_id(left)
    right_id = _card_id(right)
    return right_id in _string_list(left.get("incompatible_with")) or left_id in _string_list(right.get("incompatible_with"))


def _card_id(card: dict[str, object]) -> str:
    return str(card.get("card_id", "")).strip()


def _composition_id(request: CompositionRequest, selected_cards: list[str]) -> str:
    digest = hashlib.sha1(
        "|".join(
            [
                request.domain,
                request.format,
                request.goal,
                request.content_type,
                request.style_family,
                request.author_signature,
                *selected_cards,
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"comp_{digest}"


def _build_notes(matched_guardrails: list[dict[str, object]], unresolved_conflicts: list[str]) -> str:
    guardrail_ids = [_card_id(card) for card in matched_guardrails]
    notes: list[str] = []
    if guardrail_ids:
        notes.append(f"Selected guardrails: {', '.join(guardrail_ids)}.")
    if unresolved_conflicts:
        notes.append("Human review is required before script generation.")
    return " ".join(notes)


def _drop_empty_fields(payload: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, value in payload.items():
        if value in ("", None):
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, dict) and not value:
            continue
        cleaned[key] = value
    return cleaned


def _string_list(raw_value: object) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    return [str(item).strip() for item in raw_value if str(item).strip()]
