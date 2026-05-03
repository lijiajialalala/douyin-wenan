from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from douyin_wenan.common.csv_io import read_csv_rows
from douyin_wenan.common.csv_io import write_csv_rows
from douyin_wenan.paths import ensure_parent_dir


@dataclass(frozen=True)
class Phase3DistillationResult:
    skill_cards: list[dict[str, object]]
    anti_skill_cards: list[dict[str, object]]
    skipped_records: list[dict[str, str]]


def load_evidence_records_csv(path: Path) -> list[dict[str, str]]:
    return read_csv_rows(path)


def distill_phase3_cards(
    evidence_records: list[dict[str, str]],
    *,
    author: str = "",
) -> Phase3DistillationResult:
    target_author = author.strip()
    skill_cards: list[dict[str, object]] = []
    anti_skill_cards: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []

    for record in evidence_records:
        if target_author and (record.get("author", "") or "").strip() != target_author:
            continue
        decision = _classify_record(record)
        if decision == "skip":
            skipped.append(
                {
                    "evidence_id": (record.get("evidence_id", "") or "").strip(),
                    "reason": "insufficient_evidence_or_unsupported_kind",
                }
            )
            continue
        if decision == "skill":
            skill_cards.append(_build_skill_card(record))
            continue
        if decision == "anti_skill":
            anti_skill_cards.append(_build_anti_skill_card(record))
            continue

    return Phase3DistillationResult(
        skill_cards=skill_cards,
        anti_skill_cards=anti_skill_cards,
        skipped_records=skipped,
    )

def write_phase3_exports(
    result: Phase3DistillationResult,
    analysis_dir: Path,
    *,
    target_authors: tuple[str, ...] | None = None,
) -> dict[str, object]:
    skills_dir = analysis_dir / "assets" / "skills"
    anti_dir = analysis_dir / "assets" / "anti_skills"
    exports_dir = analysis_dir / "exports"
    effective_target_authors, replace_all = _resolve_target_authors(
        explicit_target_authors=target_authors,
        inferred_target_authors=_target_authors_from_cards(result),
    )
    summary_path = exports_dir / "phase3_candidates.csv"
    existing_summary_rows = read_csv_rows(summary_path) if summary_path.exists() else []

    _delete_replaced_author_assets(
        existing_summary_rows,
        effective_target_authors,
        replace_all=replace_all,
        skills_dir=skills_dir,
        anti_dir=anti_dir,
    )

    skill_paths: list[Path] = []
    for card in result.skill_cards:
        path = skills_dir / f"{card['card_id']}.yaml"
        _write_yaml(path, _yaml_payload(card))
        skill_paths.append(path)

    anti_paths: list[Path] = []
    for card in result.anti_skill_cards:
        path = anti_dir / f"{card['card_id']}.yaml"
        _write_yaml(path, _yaml_payload(card))
        anti_paths.append(path)

    new_summary_rows = [
        {
            "card_id": str(card["card_id"]),
            "card_kind": "skill",
            "title": str(card["title"]),
            "status": str(card["status"]),
            "layer": str(card["layer"]),
            "source_author": str(card.get("_source_author", "")),
            "evidence_refs": "|".join(str(ref) for ref in card.get("evidence_refs", [])),
        }
        for card in result.skill_cards
    ] + [
        {
            "card_id": str(card["card_id"]),
            "card_kind": "anti_skill",
            "title": str(card["title"]),
            "status": str(card["status"]),
            "layer": str(card["layer"]),
            "source_author": str(card.get("_source_author", "")),
            "evidence_refs": "|".join(str(ref) for ref in card.get("evidence_refs", [])),
        }
        for card in result.anti_skill_cards
    ]
    retained_summary_rows = [] if replace_all else [
        row
        for row in existing_summary_rows
        if not effective_target_authors or (row.get("source_author", "") or "").strip() not in effective_target_authors
    ]
    merged_summary_rows = _merge_summary_rows(retained_summary_rows, new_summary_rows)
    _write_summary(summary_path, merged_summary_rows)

    return {
        "skills": skill_paths,
        "anti_skills": anti_paths,
        "summary": summary_path,
    }


def _classify_record(record: dict[str, str]) -> str:
    confidence = (record.get("confidence_grade", "") or "").strip()
    ready = (record.get("ready_for_distillation", "") or "").strip()
    kind = (record.get("evidence_kind", "") or "").strip()
    if ready != "yes":
        return "skip"
    if confidence not in {"E2", "E3", "E4"}:
        return "skip"
    if kind == "corroborated_pattern":
        return "skill"
    if kind == "rejected_pattern":
        return "anti_skill"
    return "skip"


def _build_skill_card(record: dict[str, str]) -> dict[str, object]:
    feature_name = _text(record, "feature_name")
    feature_value = _text(record, "feature_value")
    evidence_id = _text(record, "evidence_id")
    layer = _text(record, "layer") or "general"
    status = _status_from_confidence(_text(record, "confidence_grade"))
    card_type = "signature_pattern" if layer == "author_signature" else "skill"
    author_scope = _text(record, "author") if card_type == "signature_pattern" else ""
    slots = _slots_for_feature(feature_name)
    title = _skill_title(feature_name, feature_value)
    style_family = _text(record, "style_family")
    card = {
        "card_id": _card_id("skill", evidence_id, feature_name, feature_value),
        "title": title,
        "card_type": card_type,
        "status": status,
        "layer": layer,
        "priority": _priority_for_record(record),
        "hardness": _hardness_for_feature(feature_name),
        "content_types": _list_if_text(_text(record, "content_type")),
        "formats": _list_if_text(_text(record, "format")),
        "domains": _list_if_text(_text(record, "domain")),
        "goals": _list_if_text(_text(record, "primary_goal")),
        "style_families": _list_if_text(style_family),
        "author_scope": author_scope,
        "trigger_conditions": _skill_triggers(feature_name, feature_value, record),
        "avoid_conditions": _skill_avoid_conditions(feature_name, feature_value),
        "slots": slots,
        "depends_on": [],
        "overrides": [],
        "incompatible_with": [],
        "input_context": _skill_input_context(feature_name, record),
        "execution_steps": _skill_execution_steps(feature_name, feature_value, record),
        "output_contract": _skill_output_contract(feature_name, feature_value),
        "evaluation_checks": _skill_evaluation_checks(feature_name, feature_value),
        "positive_examples": _positive_examples(record),
        "counter_examples": _skill_counter_examples(feature_name, feature_value),
        "evidence_refs": [evidence_id],
        "notes": _skill_notes(record),
        "_source_author": _text(record, "author"),
    }
    return _drop_empty_fields(card)


def _build_anti_skill_card(record: dict[str, str]) -> dict[str, object]:
    feature_name = _text(record, "feature_name")
    feature_value = _text(record, "feature_value")
    evidence_id = _text(record, "evidence_id")
    card = {
        "card_id": _card_id("anti", evidence_id, feature_name, feature_value),
        "title": _anti_skill_title(feature_name, feature_value),
        "status": _status_from_confidence(_text(record, "confidence_grade")),
        "layer": _text(record, "layer") or "general",
        "priority": _priority_for_record(record),
        "hardness": _hardness_for_feature(feature_name),
        "content_types": _list_if_text(_text(record, "content_type")),
        "formats": _list_if_text(_text(record, "format")),
        "domains": _list_if_text(_text(record, "domain")),
        "goals": _list_if_text(_text(record, "primary_goal")),
        "failure_pattern": _anti_failure_pattern(feature_name, feature_value),
        "detection_signals": _anti_detection_signals(feature_name, feature_value, record),
        "likely_causes": _anti_likely_causes(feature_name, feature_value),
        "prevention_actions": _anti_prevention_actions(feature_name, feature_value),
        "bad_examples": _positive_examples(record),
        "repair_examples": _anti_repair_examples(feature_name, feature_value),
        "evaluation_checks": _anti_evaluation_checks(feature_name, feature_value),
        "evidence_refs": [evidence_id],
        "notes": _text(record, "notes"),
        "_source_author": _text(record, "author"),
    }
    return _drop_empty_fields(card)


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    ensure_parent_dir(path)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_parent_dir(path)
    if not rows:
        write_csv_rows(path, ["card_id", "card_kind", "title", "status", "layer", "source_author", "evidence_refs"], [])
        return
    write_csv_rows(path, _summary_fieldnames(rows), rows)


def _card_id(prefix: str, evidence_id: str, feature_name: str, feature_value: str) -> str:
    digest = hashlib.sha1(f"{evidence_id}|{feature_name}|{feature_value}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _status_from_confidence(confidence: str) -> str:
    return "candidate" if confidence == "E2" else "active"


def _priority_for_record(record: dict[str, str]) -> int:
    feature_name = _text(record, "feature_name")
    confidence = _text(record, "confidence_grade")
    base = {"E2": 70, "E3": 80, "E4": 90}.get(confidence, 60)
    if feature_name in {"hook_type", "argument_shape"}:
        return base + 10
    if feature_name in {"style_family", "opening_problem_presence", "opening_payoff_presence"}:
        return base + 5
    return base


def _hardness_for_feature(feature_name: str) -> str:
    if feature_name in {"hook_type", "argument_shape", "opening_problem_presence", "opening_payoff_presence"}:
        return "required"
    if feature_name in {"style_family", "cta_type", "cta_presence"}:
        return "preferred"
    return "optional"


def _slots_for_feature(feature_name: str) -> list[str]:
    mapping = {
        "style_family": ["hook"],
        "hook_type": ["hook"],
        "opening_problem_presence": ["hook"],
        "opening_payoff_presence": ["hook"],
        "argument_shape": ["claim", "example"],
        "cta_presence": ["cta"],
        "cta_type": ["cta"],
    }
    return mapping.get(feature_name, ["claim"])


def _skill_title(feature_name: str, feature_value: str) -> str:
    mapping = {
        ("style_family", "question_hook"): "Question Hook Before Thesis Reveal",
        ("style_family", "strong_claim"): "Strong Claim Opening",
        ("argument_shape", "example_led"): "Example-Led Argument Progression",
        ("hook_type", "question"): "Direct Question Hook",
    }
    return mapping.get((feature_name, feature_value), f"Use {feature_name}={feature_value} As A Reusable Pattern")


def _anti_skill_title(feature_name: str, feature_value: str) -> str:
    mapping = {
        ("hook_type", "statement"): "Statement Hook Without Viewer Tension",
        ("cta_presence", "no"): "Missing CTA When The Goal Needs One",
    }
    return mapping.get((feature_name, feature_value), f"Avoid {feature_name}={feature_value} In Weak Patterns")


def _skill_triggers(feature_name: str, feature_value: str, record: dict[str, str]) -> list[str]:
    if feature_name == "style_family" and feature_value == "question_hook":
        return [
            "Use when the opening must surface an audience doubt before the thesis.",
            "Use when retention depends on immediate problem recognition.",
        ]
    if feature_name == "argument_shape" and feature_value == "example_led":
        return [
            "Use when the argument becomes clearer through one or more concrete examples.",
            "Use when abstract claims need grounding before the close.",
        ]
    return [
        f"Use when {feature_name}={feature_value} matches the target script need.",
        f"Use within {(_text(record, 'format') or 'the current format')} when the evidence scope is comparable.",
    ]


def _skill_avoid_conditions(feature_name: str, feature_value: str) -> list[str]:
    if feature_name == "style_family" and feature_value == "question_hook":
        return ["Avoid when the opening already contains a hard claim that should not be delayed by a question."]
    if feature_name == "argument_shape" and feature_value == "example_led":
        return ["Avoid when the format requires immediate verdict before any example expansion."]
    return []


def _skill_input_context(feature_name: str, record: dict[str, str]) -> list[str]:
    base = [
        f"Primary domain facts for {(_text(record, 'domain') or 'the target domain')}.",
        f"One clear thesis for {(_text(record, 'content_type') or 'the target content type')}.",
    ]
    if feature_name in {"style_family", "hook_type"}:
        base.append("A concrete viewer-facing doubt, tension, or problem.")
    if feature_name == "argument_shape":
        base.append("At least one concrete example that can move the claim forward.")
    return base


def _skill_execution_steps(feature_name: str, feature_value: str, record: dict[str, str]) -> list[str]:
    if feature_name == "style_family" and feature_value == "question_hook":
        return [
            "Raise a concrete audience question before giving the thesis.",
            "Answer the question by naming the real mechanism or conflict.",
            "Move into the body without adding generic warmup.",
        ]
    if feature_name == "argument_shape" and feature_value == "example_led":
        return [
            "State the claim in one line.",
            "Bring in a concrete example that proves or sharpens the claim.",
            "Use the example to re-anchor the thesis before moving on.",
        ]
    if feature_name == "hook_type" and feature_value == "question":
        return [
            "Frame the hook as one explicit question.",
            "Make sure the question carries a visible stake for the viewer.",
            "Resolve or sharpen the question before expanding background.",
        ]
    return [
        f"Apply {feature_name}={feature_value} early in its owning slot.",
        "Keep the move tied to the core claim instead of using it as decoration.",
        "Re-anchor the thesis before transitioning to the next slot.",
    ]


def _skill_output_contract(feature_name: str, feature_value: str) -> list[str]:
    if feature_name in {"style_family", "hook_type"}:
        return [
            "The hook expresses a clear viewer-facing tension.",
            "The body begins before the setup drifts into generic background.",
        ]
    if feature_name == "argument_shape":
        return [
            "At least one concrete example moves the argument forward.",
            "The example supports the thesis instead of replacing it.",
        ]
    return [f"The script visibly uses {feature_name}={feature_value} in the intended slot."]


def _skill_evaluation_checks(feature_name: str, feature_value: str) -> list[str]:
    if feature_name in {"style_family", "hook_type"}:
        return [
            "A viewer can identify the core question or conflict in the opening.",
            "The opening does not stall before the thesis arrives.",
        ]
    if feature_name == "argument_shape":
        return [
            "Examples are doing argumentative work, not just adding trivia.",
            "The thesis is still legible after the example section.",
        ]
    return [f"Check that {feature_name}={feature_value} is visible and functional in the final script."]


def _skill_counter_examples(feature_name: str, feature_value: str) -> list[str]:
    if feature_name == "style_family" and feature_value == "question_hook":
        return ["A generic opening statement that spends too long on background before revealing the question."]
    if feature_name == "argument_shape" and feature_value == "example_led":
        return ["A script that lists examples but never reconnects them to the thesis."]
    return [f"A script where {feature_name}={feature_value} is present only as surface wording with no structural effect."]


def _skill_notes(record: dict[str, str]) -> str:
    confidence = _text(record, "confidence_grade")
    if confidence == "E2":
        return "Candidate card. Evidence is meaningful but not strong enough for active default reuse yet."
    return _text(record, "notes")


def _anti_failure_pattern(feature_name: str, feature_value: str) -> str:
    if feature_name == "hook_type" and feature_value == "statement":
        return "The opening states information plainly without enough viewer tension or conflict."
    return f"The script leans on {feature_name}={feature_value} in patterns associated with weaker rows."


def _anti_detection_signals(feature_name: str, feature_value: str, record: dict[str, str]) -> list[str]:
    if feature_name == "hook_type" and feature_value == "statement":
        return [
            "The hook sounds like background exposition instead of a decision-driving tension.",
            "The script delays the real problem while opening with a flat statement.",
        ]
    return [
        f"{feature_name}={feature_value} appears in a weak opening or weak structural slot.",
        f"The same move underperformed within the compared scope {(_text(record, 'scope') or 'unknown')}.",
    ]


def _anti_likely_causes(feature_name: str, feature_value: str) -> list[str]:
    if feature_name == "hook_type" and feature_value == "statement":
        return [
            "The writer is front-loading background instead of surfacing the stake.",
            "The writer is copying calm narration without copying the stronger structure underneath it.",
        ]
    return [
        "The move was copied from surface style without checking its structural role.",
        "The script is using a habit that is too weak for the declared goal or format.",
    ]


def _anti_prevention_actions(feature_name: str, feature_value: str) -> list[str]:
    if feature_name == "hook_type" and feature_value == "statement":
        return [
            "Replace the flat statement with a concrete question, conflict, or payoff.",
            "Cut any opening sentence that does not change the viewer's reason to continue.",
        ]
    return [
        f"Reduce or remove {feature_name}={feature_value} when it weakens the owning slot.",
        "Replace the weak move with a clearer structure-first alternative.",
    ]


def _anti_repair_examples(feature_name: str, feature_value: str) -> list[str]:
    if feature_name == "hook_type" and feature_value == "statement":
        return ["If this one mechanism stays in place, the whole power structure flips against the emperor."]
    return [f"Rewrite the slot so that {feature_name}={feature_value} no longer dominates the weak pattern."]


def _anti_evaluation_checks(feature_name: str, feature_value: str) -> list[str]:
    if feature_name == "hook_type" and feature_value == "statement":
        return [
            "The hook contains a visible stake instead of flat exposition.",
            "The audience can tell why they should keep listening before the body unfolds.",
        ]
    return [f"Check that {feature_name}={feature_value} no longer weakens the owning slot."]


def _positive_examples(record: dict[str, str]) -> list[str]:
    excerpt = _text(record, "source_excerpt")
    if excerpt:
        return [excerpt]
    return [_text(record, "notes") or "See supporting evidence excerpt."]


def _list_if_text(value: str) -> list[str]:
    return [value] if value else []


def _drop_empty_fields(payload: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, value in payload.items():
        if value in ("", None):
            continue
        if isinstance(value, list) and not value:
            continue
        cleaned[key] = value
    return cleaned


def _text(record: dict[str, str], field: str) -> str:
    return (record.get(field, "") or "").strip()


def _yaml_payload(card: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in card.items() if not key.startswith("_")}


def _target_authors_from_cards(result: Phase3DistillationResult) -> tuple[str, ...]:
    authors = {
        str(card.get("_source_author", "")).strip()
        for card in [*result.skill_cards, *result.anti_skill_cards]
        if str(card.get("_source_author", "")).strip()
    }
    return tuple(sorted(authors))


def _delete_replaced_author_assets(
    existing_summary_rows: list[dict[str, str]],
    target_authors: tuple[str, ...],
    *,
    replace_all: bool,
    skills_dir: Path,
    anti_dir: Path,
) -> None:
    if replace_all:
        for base_dir in (skills_dir, anti_dir):
            if not base_dir.exists():
                continue
            for path in base_dir.glob("*.yaml"):
                path.unlink()
        return
    if not target_authors:
        return
    for row in existing_summary_rows:
        source_author = (row.get("source_author", "") or "").strip()
        if source_author not in target_authors:
            continue
        card_id = (row.get("card_id", "") or "").strip()
        card_kind = (row.get("card_kind", "") or "").strip()
        if not card_id or not card_kind:
            continue
        base_dir = skills_dir if card_kind == "skill" else anti_dir
        path = base_dir / f"{card_id}.yaml"
        if path.exists():
            path.unlink()


def _summary_fieldnames(rows: list[dict[str, str]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row.keys():
            if field in seen:
                continue
            seen.add(field)
            fieldnames.append(field)
    return fieldnames


def _merge_summary_rows(existing_rows: list[dict[str, str]], new_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    merged_by_card_id: dict[str, dict[str, str]] = {}
    for row in existing_rows + new_rows:
        card_id = (row.get("card_id", "") or "").strip()
        if not card_id:
            continue
        merged_by_card_id[card_id] = row
    return list(merged_by_card_id.values())


def _resolve_target_authors(
    *,
    explicit_target_authors: tuple[str, ...] | None,
    inferred_target_authors: tuple[str, ...],
) -> tuple[tuple[str, ...], bool]:
    if explicit_target_authors is not None:
        cleaned = tuple(sorted({author.strip() for author in explicit_target_authors if author.strip()}))
        return cleaned, False
    if inferred_target_authors:
        return inferred_target_authors, False
    return (), True
