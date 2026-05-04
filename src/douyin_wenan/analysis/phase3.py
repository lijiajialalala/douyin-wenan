from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from douyin_wenan.common.csv_io import read_csv_rows
from douyin_wenan.common.csv_io import write_csv_rows
from douyin_wenan.paths import ensure_parent_dir


SHARED_EVIDENCE_AUTHOR = "多作者"
SHARED_EVIDENCE_KINDS = {"route_foundation_pattern", "cross_author_transfer_pattern"}


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
        if target_author and not _matches_author_scope(record, target_author):
            continue
        decision, skill_subtype = _classify_record(record)
        if decision == "skip":
            skipped.append(
                {
                    "evidence_id": (record.get("evidence_id", "") or "").strip(),
                    "reason": "insufficient_evidence_or_unsupported_kind",
                }
            )
            continue
        if decision == "skill":
            skill_cards.append(_build_skill_card(record, skill_subtype=skill_subtype))
            continue
        if decision == "anti_skill":
            anti_skill_cards.append(_build_anti_skill_card(record, skill_subtype=skill_subtype))
            continue

    return Phase3DistillationResult(
        skill_cards=_consolidate_skill_cards(skill_cards),
        anti_skill_cards=_merge_equivalent_cards(anti_skill_cards),
        skipped_records=skipped,
    )


def _matches_author_scope(record: dict[str, str], target_author: str) -> bool:
    author = (record.get("author", "") or "").strip()
    return author == target_author or _is_shared_evidence_record(record)


def _is_shared_evidence_record(record: dict[str, str]) -> bool:
    return (record.get("evidence_kind", "") or "").strip() in SHARED_EVIDENCE_KINDS


def write_phase3_exports(
    result: Phase3DistillationResult,
    analysis_dir: Path,
    *,
    target_authors: tuple[str, ...] | None = None,
) -> dict[str, object]:
    skills_dir = analysis_dir / "assets" / "skills"
    anti_dir = analysis_dir / "assets" / "anti_skills"
    exports_dir = analysis_dir / "exports"
    readable_zh_dir = analysis_dir / "readable_zh"
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
            "skill_subtype": str(card.get("skill_subtype", "")),
            "title": str(card["title"]),
            "status": str(card["status"]),
            "layer": str(card["layer"]),
            "transferability_level": str(card.get("transferability_level", "")),
            "promotion_status": str(card.get("promotion_status", "")),
            "author_scope": str(card.get("author_scope", "")),
            "source_author": str(card.get("_source_author", "")),
            "evidence_refs": "|".join(str(ref) for ref in card.get("evidence_refs", [])),
        }
        for card in result.skill_cards
    ] + [
        {
            "card_id": str(card["card_id"]),
            "card_kind": "anti_skill",
            "skill_subtype": str(card.get("skill_subtype", "")),
            "title": str(card["title"]),
            "status": str(card["status"]),
            "layer": str(card["layer"]),
            "transferability_level": str(card.get("transferability_level", "")),
            "promotion_status": str(card.get("promotion_status", "")),
            "author_scope": str(card.get("author_scope", "")),
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
    readable_paths = _write_readable_zh_exports(
        readable_zh_dir,
        skill_cards=result.skill_cards,
        anti_skill_cards=result.anti_skill_cards,
        target_authors=effective_target_authors,
        replace_all=replace_all,
    )

    return {
        "skills": skill_paths,
        "anti_skills": anti_paths,
        "summary": summary_path,
        "readable_zh": readable_paths,
    }


def _classify_record(record: dict[str, str]) -> tuple[str, str]:
    confidence = (record.get("confidence_grade", "") or "").strip()
    ready = (record.get("ready_for_distillation", "") or "").strip()
    kind = (record.get("evidence_kind", "") or "").strip()
    if ready != "yes":
        return "skip", ""
    if confidence not in {"E2", "E3", "E4"}:
        return "skip", ""
    if kind == "author_foundation_pattern":
        if not _supports_positive_skill(record):
            return "skip", ""
        return "skill", "foundational_skill"
    if kind == "route_foundation_pattern":
        if not _supports_positive_skill(record):
            return "skip", ""
        return "skill", "foundational_skill"
    if kind == "differential_gain_pattern":
        if not _supports_positive_skill(record):
            return "skip", ""
        return "skill", "gain_skill"
    if kind == "cross_author_transfer_pattern":
        if not _supports_positive_skill(record):
            return "skip", ""
        return "skill", "transferable_skill"
    if kind == "negative_pattern":
        if not _supports_negative_skill(record):
            return "skip", ""
        return "anti_skill", "negative_pattern"
    return "skip", ""


def _supports_positive_skill(record: dict[str, str]) -> bool:
    feature_name = _text(record, "feature_name")
    feature_value = _text(record, "feature_value")
    allowlist = {
        "style_family": {"question_hook", "strong_claim", "contrarian_reframe", "story_led"},
        "hook_type": {"question", "claim", "scene"},
        "opening_problem_presence": {"yes"},
        "opening_payoff_presence": {"yes"},
        "argument_shape": {"example_led", "stepwise_explainer", "contrastive_argument"},
        "cta_presence": {"yes"},
        "cta_type": {"save", "follow", "interaction"},
    }
    return feature_value in allowlist.get(feature_name, set())


def _supports_negative_skill(record: dict[str, str]) -> bool:
    feature_name = _text(record, "feature_name")
    feature_value = _text(record, "feature_value")
    primary_goal = _text(record, "primary_goal")

    if feature_name == "hook_type" and feature_value == "statement":
        return True
    if feature_name == "opening_problem_presence" and feature_value == "no":
        return True
    if feature_name == "opening_payoff_presence" and feature_value == "no":
        return primary_goal in {"save", "follow", "interaction", "completion"}
    if feature_name == "argument_shape" and feature_value == "straight_explainer":
        return True
    if feature_name == "cta_presence" and feature_value == "no":
        return primary_goal in {"follow", "interaction"}
    return False


def _consolidate_skill_cards(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    return _merge_equivalent_cards(_drop_less_specific_skill_cards(cards))


def _drop_less_specific_skill_cards(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    specific_scopes: set[tuple[str, tuple[object, ...]]] = set()
    for card in cards:
        feature_name = str(card.get("_source_feature_name", ""))
        feature_value = str(card.get("_source_feature_value", ""))
        scope = _specificity_scope(card)
        if feature_name == "cta_type" and feature_value in {"save", "follow", "interaction"}:
            specific_scopes.add(("cta", scope))
        if feature_name == "style_family" and feature_value == "question_hook":
            specific_scopes.add(("question_hook", scope))
        if feature_name == "style_family" and feature_value == "strong_claim":
            specific_scopes.add(("claim_hook", scope))

    retained: list[dict[str, object]] = []
    for card in cards:
        feature_name = str(card.get("_source_feature_name", ""))
        feature_value = str(card.get("_source_feature_value", ""))
        scope = _specificity_scope(card)
        if feature_name == "cta_presence" and feature_value == "yes" and ("cta", scope) in specific_scopes:
            continue
        if feature_name == "hook_type" and feature_value == "question" and ("question_hook", scope) in specific_scopes:
            continue
        if feature_name == "hook_type" and feature_value == "claim" and ("claim_hook", scope) in specific_scopes:
            continue
        retained.append(card)
    return retained


def _specificity_scope(card: dict[str, object]) -> tuple[object, ...]:
    return (
        str(card.get("skill_subtype", "")),
        str(card.get("_source_author", "")),
        str(card.get("promotion_status", "")),
        str(card.get("transferability_level", "")),
        str(card.get("author_scope", "")),
        tuple(_object_list(card.get("content_types", []))),
        tuple(_object_list(card.get("formats", []))),
        tuple(_object_list(card.get("domains", []))),
        tuple(_object_list(card.get("goals", []))),
    )


def _merge_equivalent_cards(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    merged_by_key: dict[tuple[object, ...], dict[str, object]] = {}
    for card in cards:
        key = _equivalent_card_key(card)
        existing = merged_by_key.get(key)
        merged_by_key[key] = _copy_card(card) if existing is None else _merge_card(existing, card)
    return list(merged_by_key.values())


def _equivalent_card_key(card: dict[str, object]) -> tuple[object, ...]:
    return (
        str(card.get("card_type", "")),
        str(card.get("skill_subtype", "")),
        str(card.get("_source_author", "")),
        str(card.get("_source_feature_name", "")),
        str(card.get("_source_feature_value", "")),
        str(card.get("layer", "")),
        str(card.get("promotion_status", "")),
        str(card.get("transferability_level", "")),
        str(card.get("author_scope", "")),
        tuple(_object_list(card.get("formats", []))),
        tuple(_object_list(card.get("goals", []))),
    )


def _copy_card(card: dict[str, object]) -> dict[str, object]:
    copied: dict[str, object] = {}
    for key, value in card.items():
        copied[key] = list(value) if isinstance(value, list) else value
    return copied


def _merge_card(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    merged = _copy_card(left)
    for field in _MERGEABLE_CARD_LIST_FIELDS:
        merged[field] = _unique_strings(
            [*(_object_list(left.get(field, []))), *(_object_list(right.get(field, [])))]
        )
    merged["priority"] = max(_int_value(left.get("priority")), _int_value(right.get("priority")))
    merged["status"] = _stronger_status(str(left.get("status", "")), str(right.get("status", "")))
    return _refresh_readable_summary(merged)


_MERGEABLE_CARD_LIST_FIELDS = {
    "content_types",
    "formats",
    "domains",
    "goals",
    "style_families",
    "trigger_conditions",
    "avoid_conditions",
    "input_context",
    "execution_steps",
    "output_contract",
    "evaluation_checks",
    "counter_examples",
    "evidence_refs",
    "misuse_risks",
    "positive_examples",
    "detection_signals",
    "likely_causes",
    "prevention_actions",
    "repair_examples",
}


def _object_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _int_value(value: object) -> int:
    try:
        return int(str(value))
    except ValueError:
        return 0


def _stronger_status(left: str, right: str) -> str:
    rank = {"candidate": 1, "validated": 2, "active": 3}
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


def _refresh_readable_summary(card: dict[str, object]) -> dict[str, object]:
    feature_name = str(card.get("_source_feature_name", ""))
    feature_value = str(card.get("_source_feature_value", ""))
    if card.get("card_type") == "anti_skill" or card.get("skill_subtype") == "negative_pattern":
        card["_summary_zh"] = (
            f"{_anti_skill_title_zh(feature_name, feature_value)}。"
            f"这类模式在当前证据里更常落在弱稿一侧，适用范围：{_card_route_text_zh(card)}。"
        )
        return card
    skill_subtype = str(card.get("skill_subtype", ""))
    base = {
        "foundational_skill": "这更像该作者长期稳定在用的基础能力，不是只在高稿里偶然出现的技巧。",
        "gain_skill": "这更像高稿比低稿更常出现的增益动作，适合当成提升项来用。",
        "transferable_skill": "这条已经不只局限在单一作者，适合当成更可迁移的共性能力。",
    }.get(skill_subtype, "")
    card["_summary_zh"] = (
        f"{_skill_title_zh(feature_name, feature_value, skill_subtype=skill_subtype)}。"
        f"{base} 当前适用范围：{_card_route_text_zh(card)}。"
    )
    return card


def _build_skill_card(record: dict[str, str], *, skill_subtype: str) -> dict[str, object]:
    feature_name = _text(record, "feature_name")
    feature_value = _text(record, "feature_value")
    evidence_id = _text(record, "evidence_id")
    layer = _text(record, "layer") or "general"
    status = _status_from_confidence(_text(record, "confidence_grade"))
    card_type = "signature_pattern" if layer == "author_signature" else "skill"
    slots = _slots_for_feature(feature_name)
    title = _skill_title(feature_name, feature_value)
    style_family = _text(record, "style_family")
    transferability_level = _transferability_level(record, skill_subtype=skill_subtype)
    promotion_status = _promotion_status(record, transferability_level=transferability_level)
    author_scope = _author_scope_for_card(record, card_type=card_type, promotion_status=promotion_status)
    card = {
        "card_id": _card_id("skill", evidence_id, feature_name, feature_value),
        "title": title,
        "card_type": card_type,
        "skill_subtype": skill_subtype,
        "status": status,
        "layer": layer,
        "priority": _priority_for_record(record),
        "hardness": _hardness_for_feature(feature_name),
        "transferability_level": transferability_level,
        "promotion_status": promotion_status,
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
        "production_actionability": _production_actionability(feature_name),
        "misuse_risks": _misuse_risks(record, transferability_level=transferability_level),
        "positive_examples": _positive_examples(record),
        "counter_examples": _skill_counter_examples(feature_name, feature_value),
        "evidence_refs": [evidence_id],
        "notes": _skill_notes(record),
        "_title_zh": _skill_title_zh(feature_name, feature_value, skill_subtype=skill_subtype),
        "_summary_zh": _skill_summary_zh(feature_name, feature_value, record, skill_subtype=skill_subtype),
        "_source_feature_name": feature_name,
        "_source_feature_value": feature_value,
        "_source_author": _text(record, "author"),
    }
    return _drop_empty_fields(card)


def _build_anti_skill_card(record: dict[str, str], *, skill_subtype: str) -> dict[str, object]:
    feature_name = _text(record, "feature_name")
    feature_value = _text(record, "feature_value")
    evidence_id = _text(record, "evidence_id")
    transferability_level = _transferability_level(record, skill_subtype=skill_subtype)
    promotion_status = _promotion_status(record, transferability_level=transferability_level)
    author_scope = _author_scope_for_card(record, card_type="anti_skill", promotion_status=promotion_status)
    card = {
        "card_id": _card_id("anti", evidence_id, feature_name, feature_value),
        "title": _anti_skill_title(feature_name, feature_value),
        "card_type": "anti_skill",
        "skill_subtype": skill_subtype,
        "status": _status_from_confidence(_text(record, "confidence_grade")),
        "layer": _text(record, "layer") or "general",
        "priority": _priority_for_record(record),
        "hardness": _hardness_for_feature(feature_name),
        "transferability_level": transferability_level,
        "promotion_status": promotion_status,
        "content_types": _list_if_text(_text(record, "content_type")),
        "formats": _list_if_text(_text(record, "format")),
        "domains": _list_if_text(_text(record, "domain")),
        "goals": _list_if_text(_text(record, "primary_goal")),
        "author_scope": author_scope,
        "failure_pattern": _anti_failure_pattern(feature_name, feature_value),
        "detection_signals": _anti_detection_signals(feature_name, feature_value, record),
        "likely_causes": _anti_likely_causes(feature_name, feature_value),
        "prevention_actions": _anti_prevention_actions(feature_name, feature_value),
        "bad_examples": _positive_examples(record),
        "repair_examples": _anti_repair_examples(feature_name, feature_value),
        "evaluation_checks": _anti_evaluation_checks(feature_name, feature_value),
        "production_actionability": "direct",
        "misuse_risks": _misuse_risks(record, transferability_level=transferability_level),
        "evidence_refs": [evidence_id],
        "notes": _text(record, "notes"),
        "_title_zh": _anti_skill_title_zh(feature_name, feature_value),
        "_summary_zh": _anti_skill_summary_zh(feature_name, feature_value, record),
        "_source_feature_name": feature_name,
        "_source_feature_value": feature_value,
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


def _transferability_level(record: dict[str, str], *, skill_subtype: str) -> str:
    layer = _text(record, "layer")
    evidence_kind = _text(record, "evidence_kind")
    format_name = _text(record, "format")
    if layer == "author_signature":
        return "author_signature_overlay"
    if evidence_kind == "cross_author_transfer_pattern" or skill_subtype == "transferable_skill":
        return "cross_domain_rhetorical"
    if format_name in {"debate_showdown", "list_countdown"}:
        return "format_specific"
    if _text(record, "content_type"):
        return "content_type_specific"
    if format_name:
        return "format_specific"
    if _text(record, "domain"):
        return "domain_specific"
    return "general_guardrail"


def _promotion_status(record: dict[str, str], *, transferability_level: str) -> str:
    evidence_kind = _text(record, "evidence_kind")
    confidence = _text(record, "confidence_grade")
    if evidence_kind == "route_foundation_pattern":
        return "route_validated"
    if transferability_level == "general_guardrail" and confidence in {"E3", "E4"}:
        return "global_guardrail"
    if evidence_kind == "cross_author_transfer_pattern" or confidence == "E4":
        return "cross_route_validated"
    if confidence == "E3":
        return "route_validated"
    return "author_local"


def _author_scope_for_card(record: dict[str, str], *, card_type: str, promotion_status: str) -> str:
    if card_type == "signature_pattern" or promotion_status == "author_local":
        return _text(record, "author")
    return ""


def _misuse_risks(record: dict[str, str], *, transferability_level: str) -> list[str]:
    feature_name = _text(record, "feature_name")
    feature_value = _text(record, "feature_value")
    risks = ["Do not apply outside the listed routing scope without fresh evidence."]
    if transferability_level == "content_type_specific":
        risks.append("May fail when copied into a different content task even if the wording sounds reusable.")
    if transferability_level == "format_specific":
        risks.append("May distort formats with different pacing, slot order, or viewer payoff.")
    if transferability_level == "domain_specific":
        risks.append("May overfit to one domain's material logic and evidence style.")
    if transferability_level == "author_signature_overlay":
        risks.append("Treat as an author flavor overlay, not as a structural rule.")
    if feature_name in {"style_family", "hook_type"}:
        risks.append("Do not force the opening style when the format needs a stronger structural setup.")
    if feature_name == "cta_presence" or feature_name == "cta_type":
        risks.append("Do not add a CTA when the target goal does not need an explicit action.")
    if feature_name == "hook_type" and feature_value == "statement":
        risks.append("A statement opening is only weak when it lacks viewer tension, not by default.")
    if _text(record, "domain") == "history":
        risks.append("May overfit to historical narration and weaken lighter or visual-led formats.")
    return _unique_strings(risks)


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
        ("style_family", "contrarian_reframe"): "Contrarian Reframe Opening",
        ("style_family", "story_led"): "Story-Led Scene Opening",
        ("argument_shape", "example_led"): "Example-Led Argument Progression",
        ("argument_shape", "stepwise_explainer"): "Stepwise Argument Build",
        ("argument_shape", "contrastive_argument"): "Contrastive Argument Framing",
        ("hook_type", "question"): "Direct Question Hook",
        ("hook_type", "claim"): "Strong Claim Hook",
        ("hook_type", "scene"): "Scene-Setting Hook",
        ("opening_problem_presence", "yes"): "Open With A Concrete Viewer Problem",
        ("opening_payoff_presence", "yes"): "Signal The Payoff Early",
        ("cta_presence", "yes"): "Close With An Explicit Viewer Action",
        ("cta_type", "save"): "Save-Oriented Close",
        ("cta_type", "follow"): "Follow-Oriented Close",
        ("cta_type", "interaction"): "Discussion-Oriented Close",
    }
    return mapping.get((feature_name, feature_value), f"Use {feature_name}={feature_value} As A Reusable Pattern")


def _skill_title_zh(feature_name: str, feature_value: str, *, skill_subtype: str) -> str:
    mapping = {
        ("style_family", "question_hook"): "先提问题，再亮观点",
        ("style_family", "strong_claim"): "开头先下明确判断",
        ("style_family", "contrarian_reframe"): "先反常识，再展开解释",
        ("style_family", "story_led"): "先铺一个具体场景",
        ("argument_shape", "example_led"): "用例子带动论证推进",
        ("argument_shape", "stepwise_explainer"): "按步骤拆开讲清楚",
        ("argument_shape", "contrastive_argument"): "用对比把观点打透",
        ("hook_type", "question"): "用明确问题做开头钩子",
        ("hook_type", "claim"): "用强判断做开头钩子",
        ("hook_type", "scene"): "用场景起手",
        ("opening_problem_presence", "yes"): "开头先点出观众能感知的问题",
        ("opening_payoff_presence", "yes"): "开头提前交代能得到什么",
        ("cta_presence", "yes"): "结尾给出明确动作",
        ("cta_type", "save"): "结尾收成收藏动作",
        ("cta_type", "follow"): "结尾收成关注动作",
        ("cta_type", "interaction"): "结尾收成评论互动动作",
    }
    title = mapping.get((feature_name, feature_value), f"使用 {feature_name}={feature_value} 这种结构动作")
    if skill_subtype == "foundational_skill":
        return f"基础能力：{title}"
    if skill_subtype == "transferable_skill":
        return f"可迁移能力：{title}"
    return f"增益能力：{title}"


def _anti_skill_title(feature_name: str, feature_value: str) -> str:
    mapping = {
        ("hook_type", "statement"): "Statement Hook Without Viewer Tension",
        ("opening_problem_presence", "no"): "Opening Without A Viewer Problem",
        ("opening_payoff_presence", "no"): "Opening Without A Clear Payoff",
        ("argument_shape", "straight_explainer"): "Flat Explanation Without Progression",
        ("cta_presence", "no"): "Missing CTA When The Goal Needs One",
    }
    return mapping.get((feature_name, feature_value), f"Avoid {feature_name}={feature_value} In Weak Patterns")


def _anti_skill_title_zh(feature_name: str, feature_value: str) -> str:
    mapping = {
        ("hook_type", "statement"): "不要用平铺直叙的弱开头",
        ("opening_problem_presence", "no"): "开头不要缺少明确问题",
        ("opening_payoff_presence", "no"): "开头不要只铺垫不交代看点",
        ("argument_shape", "straight_explainer"): "不要一路平铺解释到底",
        ("cta_presence", "no"): "该收口时不要没有动作",
    }
    return mapping.get((feature_name, feature_value), f"避免 {feature_name}={feature_value} 这种弱稿模式")


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


def _production_actionability(feature_name: str) -> str:
    if feature_name in {
        "style_family",
        "hook_type",
        "opening_problem_presence",
        "opening_payoff_presence",
        "argument_shape",
        "cta_presence",
        "cta_type",
    }:
        return "direct"
    return "needs_translation"


def _anti_failure_pattern(feature_name: str, feature_value: str) -> str:
    if feature_name == "hook_type" and feature_value == "statement":
        return "The opening states information plainly without enough viewer tension or conflict."
    if feature_name == "opening_problem_presence" and feature_value == "no":
        return "The opening does not name a viewer-facing problem, so the audience has little reason to lean in."
    if feature_name == "opening_payoff_presence" and feature_value == "no":
        return "The opening delays the payoff, so the value of continuing is unclear."
    if feature_name == "argument_shape" and feature_value == "straight_explainer":
        return "The body explains in a flat line without enough progression, contrast, or example movement."
    return f"The script leans on {feature_name}={feature_value} in patterns associated with weaker rows."


def _anti_detection_signals(feature_name: str, feature_value: str, record: dict[str, str]) -> list[str]:
    if feature_name == "hook_type" and feature_value == "statement":
        return [
            "The hook sounds like background exposition instead of a decision-driving tension.",
            "The script delays the real problem while opening with a flat statement.",
        ]
    if feature_name == "opening_problem_presence" and feature_value == "no":
        return [
            "The first few lines do not tell the viewer what problem or doubt is being solved.",
            "The opening sounds like the author is introducing a topic for themselves.",
        ]
    if feature_name == "opening_payoff_presence" and feature_value == "no":
        return [
            "The first few lines do not tell the viewer what they will gain.",
            "The opening asks for attention before making the payoff visible.",
        ]
    if feature_name == "argument_shape" and feature_value == "straight_explainer":
        return [
            "The body keeps explaining without clear steps, contrast, or example-driven turns.",
            "The middle section has no obvious progression node.",
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
    if feature_name == "opening_problem_presence" and feature_value == "no":
        return [
            "The writer starts from the topic instead of the viewer's concrete doubt.",
            "The script assumes the audience already cares before it earns that attention.",
        ]
    if feature_name == "opening_payoff_presence" and feature_value == "no":
        return [
            "The writer is saving the value promise too late.",
            "The opening has information but no clear reason to keep listening.",
        ]
    if feature_name == "argument_shape" and feature_value == "straight_explainer":
        return [
            "The writer is treating explanation as a sequence of facts instead of a guided progression.",
            "The body lacks a planned step, contrast, or example rhythm.",
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
    if feature_name == "opening_problem_presence" and feature_value == "no":
        return [
            "Name one concrete viewer-facing problem in the first three to five lines.",
            "Make the next paragraph answer, sharpen, or complicate that problem.",
        ]
    if feature_name == "opening_payoff_presence" and feature_value == "no":
        return [
            "State the payoff early in a specific sentence.",
            "Make sure the body actually delivers the promised payoff.",
        ]
    if feature_name == "argument_shape" and feature_value == "straight_explainer":
        return [
            "Turn the body into steps, contrast, or example-led movement.",
            "Add a clear re-anchor sentence before moving to the close.",
        ]
    return [
        f"Reduce or remove {feature_name}={feature_value} when it weakens the owning slot.",
        "Replace the weak move with a clearer structure-first alternative.",
    ]


def _anti_repair_examples(feature_name: str, feature_value: str) -> list[str]:
    if feature_name == "hook_type" and feature_value == "statement":
        return ["If this one mechanism stays in place, the whole power structure flips against the emperor."]
    if feature_name == "opening_problem_presence" and feature_value == "no":
        return ["Why does a smart person keep making the same bad decision after seeing the cost?"]
    if feature_name == "opening_payoff_presence" and feature_value == "no":
        return ["In the next two minutes, you will understand why this choice looked irrational but was structurally inevitable."]
    if feature_name == "argument_shape" and feature_value == "straight_explainer":
        return ["First look at the rule, then the exception, and finally the moment where the exception becomes the real rule."]
    return [f"Rewrite the slot so that {feature_name}={feature_value} no longer dominates the weak pattern."]


def _anti_evaluation_checks(feature_name: str, feature_value: str) -> list[str]:
    if feature_name == "hook_type" and feature_value == "statement":
        return [
            "The hook contains a visible stake instead of flat exposition.",
            "The audience can tell why they should keep listening before the body unfolds.",
        ]
    if feature_name == "opening_problem_presence" and feature_value == "no":
        return [
            "The opening names a concrete viewer-facing problem.",
            "The body visibly works on that problem instead of drifting into topic introduction.",
        ]
    if feature_name == "opening_payoff_presence" and feature_value == "no":
        return [
            "The opening makes the payoff visible.",
            "The body delivers the payoff instead of changing the promise midstream.",
        ]
    if feature_name == "argument_shape" and feature_value == "straight_explainer":
        return [
            "The body now has clear progression nodes.",
            "The explanation no longer reads like one flat chain of facts.",
        ]
    return [f"Check that {feature_name}={feature_value} no longer weakens the owning slot."]


def _positive_examples(record: dict[str, str]) -> list[str]:
    excerpt = _text(record, "source_excerpt")
    if excerpt:
        return [excerpt]
    return [_text(record, "notes") or "See supporting evidence excerpt."]


def _skill_summary_zh(feature_name: str, feature_value: str, record: dict[str, str], *, skill_subtype: str) -> str:
    route = _route_text_zh(record)
    base = {
        "foundational_skill": "这更像该作者长期稳定在用的基础能力，不是只在高稿里偶然出现的技巧。",
        "gain_skill": "这更像高稿比低稿更常出现的增益动作，适合当成提升项来用。",
        "transferable_skill": "这条已经不只局限在单一作者，适合当成更可迁移的共性能力。",
    }.get(skill_subtype, "")
    return f"{_skill_title_zh(feature_name, feature_value, skill_subtype=skill_subtype)}。{base} 当前适用范围：{route}。"


def _anti_skill_summary_zh(feature_name: str, feature_value: str, record: dict[str, str]) -> str:
    return (
        f"{_anti_skill_title_zh(feature_name, feature_value)}。"
        f"这类模式在当前证据里更常落在弱稿一侧，适用范围：{_route_text_zh(record)}。"
    )


def _route_text_zh(record: dict[str, str]) -> str:
    content_type = _enum_zh(_text(record, "content_type")) or "未指定内容类型"
    format_value = _enum_zh(_text(record, "format")) or "未指定形式"
    goal = _enum_zh(_text(record, "primary_goal")) or "未指定目标"
    domain = _enum_zh(_text(record, "domain")) or "未指定领域"
    return f"内容类型={content_type}，形式={format_value}，目标={goal}，领域={domain}"


def _list_if_text(value: str) -> list[str]:
    return [value] if value else []


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique


def _drop_empty_fields(payload: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, value in payload.items():
        if value in ("", None):
            continue
        if isinstance(value, list) and not value:
            continue
        cleaned[key] = value
    return cleaned


def _write_readable_zh_exports(
    readable_zh_dir: Path,
    *,
    skill_cards: list[dict[str, object]],
    anti_skill_cards: list[dict[str, object]],
    target_authors: tuple[str, ...],
    replace_all: bool,
) -> dict[str, Path]:
    skill_csv_path = readable_zh_dir / "skills_zh.csv"
    anti_csv_path = readable_zh_dir / "anti_skills_zh.csv"
    skill_md_path = readable_zh_dir / "skills_zh.md"
    anti_md_path = readable_zh_dir / "anti_skills_zh.md"

    skill_rows = [_readable_skill_row(card) for card in skill_cards]
    anti_rows = [_readable_anti_skill_row(card) for card in anti_skill_cards]
    existing_skill_rows = read_csv_rows(skill_csv_path) if skill_csv_path.exists() else []
    existing_anti_rows = read_csv_rows(anti_csv_path) if anti_csv_path.exists() else []
    retained_skill_rows = [] if replace_all else [
        row
        for row in existing_skill_rows
        if not target_authors or (row.get("作者来源", "") or "").strip() not in target_authors
    ]
    retained_anti_rows = [] if replace_all else [
        row
        for row in existing_anti_rows
        if not target_authors or (row.get("作者来源", "") or "").strip() not in target_authors
    ]
    merged_skill_rows = _merge_readable_rows(retained_skill_rows, skill_rows)
    merged_anti_rows = _merge_readable_rows(retained_anti_rows, anti_rows)

    ensure_parent_dir(skill_csv_path)
    write_csv_rows(skill_csv_path, _summary_fieldnames(merged_skill_rows), merged_skill_rows)
    write_csv_rows(anti_csv_path, _summary_fieldnames(merged_anti_rows), merged_anti_rows)
    skill_md_path.write_text(_render_readable_markdown("正向技能", merged_skill_rows), encoding="utf-8")
    anti_md_path.write_text(_render_readable_markdown("反面禁忌", merged_anti_rows), encoding="utf-8")
    return {
        "skills_csv": skill_csv_path,
        "anti_skills_csv": anti_csv_path,
        "skills_md": skill_md_path,
        "anti_skills_md": anti_md_path,
    }


def _readable_skill_row(card: dict[str, object]) -> dict[str, str]:
    feature_name = str(card.get("_source_feature_name", ""))
    feature_value = str(card.get("_source_feature_value", ""))
    return {
        "系统卡片ID": str(card.get("card_id", "")),
        "卡片类型": "正向技能",
        "技能子类": _skill_subtype_zh(str(card.get("skill_subtype", ""))),
        "状态": _status_zh(str(card.get("status", ""))),
        "作者来源": str(card.get("_source_author", "")),
        "中文标题": str(card.get("_title_zh", "")),
        "适用层级": _layer_zh(str(card.get("layer", ""))),
        "迁移层级": _transferability_level_zh(str(card.get("transferability_level", ""))),
        "验证范围": _promotion_status_zh(str(card.get("promotion_status", ""))),
        "适用内容类型": _join_zh(card.get("content_types", [])),
        "适用形式": _join_zh(card.get("formats", [])),
        "适用领域": _join_zh(card.get("domains", [])),
        "适用目标": _join_zh(card.get("goals", [])),
        "误用风险": "；".join(str(item) for item in card.get("misuse_risks", [])),
        "何时使用": "；".join(_zh_skill_triggers(feature_name, feature_value, card)),
        "如何执行": "；".join(_zh_skill_execution_steps(feature_name, feature_value, card)),
        "输出要求": "；".join(_zh_skill_output_contract(feature_name, feature_value)),
        "检查方式": "；".join(_zh_skill_evaluation_checks(feature_name, feature_value)),
        "中文说明": str(card.get("_summary_zh", "")),
        "证据ID": " | ".join(str(item) for item in card.get("evidence_refs", [])),
    }


def _readable_anti_skill_row(card: dict[str, object]) -> dict[str, str]:
    feature_name = str(card.get("_source_feature_name", ""))
    feature_value = str(card.get("_source_feature_value", ""))
    return {
        "系统卡片ID": str(card.get("card_id", "")),
        "卡片类型": "反面禁忌",
        "技能子类": "失败模式",
        "状态": _status_zh(str(card.get("status", ""))),
        "作者来源": str(card.get("_source_author", "")),
        "中文标题": str(card.get("_title_zh", "")),
        "适用层级": _layer_zh(str(card.get("layer", ""))),
        "迁移层级": _transferability_level_zh(str(card.get("transferability_level", ""))),
        "验证范围": _promotion_status_zh(str(card.get("promotion_status", ""))),
        "适用内容类型": _join_zh(card.get("content_types", [])),
        "适用形式": _join_zh(card.get("formats", [])),
        "适用领域": _join_zh(card.get("domains", [])),
        "适用目标": _join_zh(card.get("goals", [])),
        "误用风险": "；".join(str(item) for item in card.get("misuse_risks", [])),
        "失败表现": _zh_anti_failure_pattern(feature_name, feature_value),
        "识别信号": "；".join(_zh_anti_detection_signals(feature_name, feature_value)),
        "修正动作": "；".join(_zh_anti_prevention_actions(feature_name, feature_value)),
        "检查方式": "；".join(_zh_anti_evaluation_checks(feature_name, feature_value)),
        "中文说明": str(card.get("_summary_zh", "")),
        "证据ID": " | ".join(str(item) for item in card.get("evidence_refs", [])),
    }


def _render_readable_markdown(title: str, rows: list[dict[str, str]]) -> str:
    lines = [f"# {title}", ""]
    if not rows:
        lines.append("暂无导出结果。")
        lines.append("")
        return "\n".join(lines)
    for row in rows:
        heading = row.get("中文标题") or row.get("英文标题") or row.get("卡片ID", "")
        lines.append(f"## {heading}")
        for key, value in row.items():
            if key == "中文标题":
                continue
            if not value:
                continue
            lines.append(f"- {key}：{value}")
        lines.append("")
    return "\n".join(lines)


def _merge_readable_rows(existing_rows: list[dict[str, str]], new_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    merged_by_card_id: dict[str, dict[str, str]] = {}
    for row in existing_rows + new_rows:
        card_id = (row.get("系统卡片ID", "") or "").strip()
        if not card_id:
            continue
        merged_by_card_id[card_id] = row
    return list(merged_by_card_id.values())


def _join_zh(values: object) -> str:
    if not isinstance(values, list):
        return ""
    return " / ".join(_enum_zh(str(value)) for value in values if str(value).strip())


def _zh_skill_triggers(feature_name: str, feature_value: str, card: dict[str, object]) -> list[str]:
    route = _card_route_text_zh(card)
    mapping = {
        ("style_family", "question_hook"): ["适合需要先把观众疑问抛出来，再进入核心观点的长口播。", route],
        ("style_family", "strong_claim"): ["适合需要先下判断、再解释原因的内容。", route],
        ("style_family", "contrarian_reframe"): ["适合先打破观众旧认知，再重建解释框架的内容。", route],
        ("style_family", "story_led"): ["适合需要先用一个具体场景把人带进去的内容。", route],
        ("hook_type", "question"): ["适合开头就要把观众拉进问题里的内容。", route],
        ("hook_type", "claim"): ["适合开头先亮立场、先给判断的内容。", route],
        ("hook_type", "scene"): ["适合靠画面感或情境感起手的内容。", route],
        ("opening_problem_presence", "yes"): ["适合需要快速建立代入感和痛点感的内容。", route],
        ("opening_payoff_presence", "yes"): ["适合一开头就要告诉观众能得到什么的内容。", route],
        ("argument_shape", "example_led"): ["适合抽象观点需要用例子撑住的内容。", route],
        ("argument_shape", "stepwise_explainer"): ["适合需要分层拆开、逐步讲透的内容。", route],
        ("argument_shape", "contrastive_argument"): ["适合用对比让观点更清楚的内容。", route],
        ("cta_presence", "yes"): ["适合目标明确需要收动作的内容。", route],
        ("cta_type", "save"): ["适合知识密度高、希望用户收藏回看的内容。", route],
        ("cta_type", "follow"): ["适合人设或系列内容，希望用户继续跟更后续的内容。", route],
        ("cta_type", "interaction"): ["适合需要评论区承接讨论或争议的内容。", route],
    }
    return mapping.get((feature_name, feature_value), [f"适合使用 {feature_name}={feature_value} 这类结构动作时。", route])


def _zh_skill_execution_steps(feature_name: str, feature_value: str, card: dict[str, object]) -> list[str]:
    mapping = {
        ("style_family", "question_hook"): ["开头先抛一个具体问题。", "紧接着给出真正的矛盾或机制。", "不要在问题和正文之间塞太多空铺垫。"],
        ("style_family", "strong_claim"): ["开头先下一个明确判断。", "后面立刻补原因或证据。", "不要只喊观点不展开。"],
        ("style_family", "contrarian_reframe"): ["先指出多数人的常见误解。", "再给出真正的解释框架。", "后文围绕这个反转继续推进。"],
        ("style_family", "story_led"): ["先给一个具体场景或瞬间。", "让场景自然引出主题。", "不要只讲故事不回到观点。"],
        ("hook_type", "question"): ["开头用一句明确问题起手。", "问题里要带观众关心的利害点。", "正文尽快回应或升级这个问题。"],
        ("hook_type", "claim"): ["开头直接亮判断。", "第二步补解释。", "避免只剩口号。"],
        ("hook_type", "scene"): ["开头先落一个画面或情境。", "快速让场景服务主题。", "不要让场景喧宾夺主。"],
        ("opening_problem_presence", "yes"): ["前 3 到 5 句内点出观众能感知的问题。", "问题要具体，不要泛泛而谈。", "后文围绕这个问题推进。"],
        ("opening_payoff_presence", "yes"): ["前面直接告诉观众能看懂什么。", "收益说清楚但不要夸张。", "后文真的兑现这个收益。"],
        ("argument_shape", "example_led"): ["先给观点。", "再上一个具体例子。", "最后把例子重新扣回观点。"],
        ("argument_shape", "stepwise_explainer"): ["把内容拆成清晰的 2 到 4 步。", "每一步只讲一个推进点。", "讲完一步再进入下一步。"],
        ("argument_shape", "contrastive_argument"): ["先摆出两个对象或两个方向。", "逐项对比差异。", "最后明确哪一边更成立以及为什么。"],
        ("cta_presence", "yes"): ["正文收尾时给出明确动作。", "动作要和正文价值一致。", "不要突然硬切。"],
        ("cta_type", "save"): ["把结尾收成收藏动作。", "强调这条内容适合回看。", "不要空喊记得收藏。"],
        ("cta_type", "follow"): ["把结尾收成关注动作。", "说明后续还有什么延展内容。", "让关注理由具体。"],
        ("cta_type", "interaction"): ["把结尾收成评论或讨论动作。", "问题要具体。", "让互动和正文核心矛盾一致。"],
    }
    return mapping.get((feature_name, feature_value), ["把这个结构动作放到它该在的位置。", "让它服务主观点，不要只做表面装饰。", "完成后再顺势进入下一段。"])


def _zh_skill_output_contract(feature_name: str, feature_value: str) -> list[str]:
    mapping = {
        ("style_family", "question_hook"): ["观众能立刻听出问题是什么。", "问题后很快进入正文，不拖。"],
        ("hook_type", "question"): ["开头有明确问题。", "问题不是摆设，后文会回应。"],
        ("hook_type", "claim"): ["开头有明确判断。", "判断后跟得上解释。"],
        ("opening_problem_presence", "yes"): ["开头明确出现观众问题。", "问题能带动继续看下去。"],
        ("opening_payoff_presence", "yes"): ["开头就说清楚能得到什么。", "后文兑现承诺。"],
        ("argument_shape", "example_led"): ["例子确实在推进论证。", "例子讲完还能回到观点。"],
        ("argument_shape", "stepwise_explainer"): ["结构层次清楚。", "每一步都在推进。"],
        ("argument_shape", "contrastive_argument"): ["对比对象清晰。", "比较维度明确。"],
        ("cta_presence", "yes"): ["结尾有明确动作。", "动作和正文一致。"],
    }
    return mapping.get((feature_name, feature_value), [f"成稿里能明显看到 {feature_name}={feature_value} 这个动作。"])


def _zh_skill_evaluation_checks(feature_name: str, feature_value: str) -> list[str]:
    mapping = {
        ("style_family", "question_hook"): ["观众能马上知道问题点。", "开头没有空铺垫。"],
        ("hook_type", "question"): ["问题是否具体。", "问题是否承接正文。"],
        ("hook_type", "claim"): ["判断是否清楚。", "判断后是否紧跟解释。"],
        ("opening_problem_presence", "yes"): ["问题是否在前面几句内出现。", "问题是否能让观众继续听。"],
        ("opening_payoff_presence", "yes"): ["收益是否说清楚。", "收益是否在正文里兑现。"],
        ("argument_shape", "example_led"): ["例子有没有服务观点。", "例子讲完有没有扣回主线。"],
        ("argument_shape", "stepwise_explainer"): ["层次是否清楚。", "有没有某一步明显断掉。"],
        ("argument_shape", "contrastive_argument"): ["对比是否清楚。", "结论是否明确。"],
        ("cta_presence", "yes"): ["动作是否明确。", "动作是否自然。"],
    }
    return mapping.get((feature_name, feature_value), ["检查这个动作是不是只停留在表面词句，没有真正起结构作用。"])


def _zh_anti_failure_pattern(feature_name: str, feature_value: str) -> str:
    mapping = {
        ("hook_type", "statement"): "开头只是平铺信息，没有把观众拉进矛盾里。",
        ("opening_problem_presence", "no"): "开头没有先点出观众问题，导致代入感不足。",
        ("opening_payoff_presence", "no"): "开头没有提前交代收益，导致继续看的理由不够强。",
        ("argument_shape", "straight_explainer"): "正文一路平讲，没有形成推进或转折。",
    }
    return mapping.get((feature_name, feature_value), f"{feature_name}={feature_value} 这类结构动作更常出现在弱稿模式里。")


def _zh_anti_detection_signals(feature_name: str, feature_value: str) -> list[str]:
    mapping = {
        ("hook_type", "statement"): ["开头像背景介绍。", "前面几句没有明显矛盾点。"],
        ("opening_problem_presence", "no"): ["开头听完还不知道观众的问题是什么。", "内容像作者在自说自话。"],
        ("opening_payoff_presence", "no"): ["开头听完还不知道这一条能带来什么。", "收益感弱。"],
        ("argument_shape", "straight_explainer"): ["内容一直在平推。", "中段没有明显推进节点。"],
    }
    return mapping.get((feature_name, feature_value), ["这个动作在弱稿里反复出现。", "它削弱了当前槽位本来该承担的作用。"])


def _zh_anti_prevention_actions(feature_name: str, feature_value: str) -> list[str]:
    mapping = {
        ("hook_type", "statement"): ["把平叙句改成问题、判断或冲突。", "删掉没有 stakes 的开头背景。"],
        ("opening_problem_presence", "no"): ["前 3 到 5 句内补一个具体问题。", "让观众先知道这条要解决什么。"],
        ("opening_payoff_presence", "no"): ["开头补一句明确收益。", "让观众知道看完能得到什么。"],
        ("argument_shape", "straight_explainer"): ["把正文拆成步骤、对比或例子推进。", "不要只靠平讲撑完全程。"],
    }
    return mapping.get((feature_name, feature_value), ["减少这种弱动作。", "换成更能承担结构任务的写法。"])


def _zh_anti_evaluation_checks(feature_name: str, feature_value: str) -> list[str]:
    mapping = {
        ("hook_type", "statement"): ["开头是否已经有 tension。", "观众是否有继续看的理由。"],
        ("opening_problem_presence", "no"): ["问题是否已提前出现。", "观众是否更容易代入。"],
        ("opening_payoff_presence", "no"): ["收益是否已交代。", "开头是否更有继续看的理由。"],
        ("argument_shape", "straight_explainer"): ["正文是否有推进节点。", "听感是否不再像平铺直叙。"],
    }
    return mapping.get((feature_name, feature_value), ["检查这类弱模式是否已经不再主导当前槽位。"])


def _card_route_text_zh(card: dict[str, object]) -> str:
    return (
        f"适用内容类型={_join_zh(card.get('content_types', [])) or '未指定'}，"
        f"形式={_join_zh(card.get('formats', [])) or '未指定'}，"
        f"目标={_join_zh(card.get('goals', [])) or '未指定'}，"
        f"领域={_join_zh(card.get('domains', [])) or '未指定'}"
    )


def _skill_subtype_zh(value: str) -> str:
    mapping = {
        "foundational_skill": "基础能力",
        "gain_skill": "增益能力",
        "transferable_skill": "可迁移能力",
    }
    return mapping.get(value, value)


def _layer_zh(value: str) -> str:
    mapping = {
        "general": "通用层",
        "content_type": "内容类型层",
        "style_family": "风格层",
        "author_signature": "作者特征层",
        "cross_layer": "跨层",
    }
    return mapping.get(value, value)


def _transferability_level_zh(value: str) -> str:
    mapping = {
        "general_guardrail": "通用底线",
        "cross_domain_rhetorical": "跨领域修辞",
        "format_specific": "形式专属",
        "content_type_specific": "内容类型专属",
        "domain_specific": "领域专属",
        "author_signature_overlay": "作者签名覆盖",
    }
    return mapping.get(value, value)


def _promotion_status_zh(value: str) -> str:
    mapping = {
        "author_local": "作者局部",
        "route_validated": "同路由验证",
        "cross_route_validated": "跨路由验证",
        "global_guardrail": "全局底线",
    }
    return mapping.get(value, value)


def _enum_zh(value: str) -> str:
    mapping = {
        "concept_explainer": "概念拆解",
        "comparison_review": "对比评述",
        "method_walkthrough": "方法/机制拆解",
        "historical_interpretation": "历史解读",
        "book_digest": "书摘解读",
        "long_explainer": "长讲解",
        "short_monologue": "短口播",
        "list_countdown": "列表式结构",
        "debate_showdown": "对抗/对决",
        "history": "历史",
        "philosophy": "哲学",
        "cognition": "认知",
        "books": "书籍",
        "ai": "AI",
        "politics": "政治",
        "business": "商业",
        "science": "科学",
        "save": "收藏",
        "follow": "关注",
        "interaction": "互动",
        "completion": "完播",
    }
    return mapping.get(value, value)


def _status_zh(value: str) -> str:
    mapping = {
        "candidate": "候选",
        "validated": "已验证",
        "active": "启用",
        "deprecated": "弃用",
    }
    return mapping.get(value, value)


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
        cleaned = _with_shared_evidence_target(explicit_target_authors)
        return (cleaned, False) if cleaned else ((), True)
    return (), True


def _with_shared_evidence_target(target_authors: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = {author.strip() for author in target_authors if author.strip()}
    if cleaned:
        cleaned.add(SHARED_EVIDENCE_AUTHOR)
    return tuple(sorted(cleaned))
