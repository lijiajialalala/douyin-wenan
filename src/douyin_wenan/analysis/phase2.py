from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median

from douyin_wenan.common.csv_io import read_csv_rows
from douyin_wenan.common.csv_io import write_csv_rows
from douyin_wenan.common.text_io import compact_char_count, count_question_marks, parse_transcript_header
from douyin_wenan.paths import ensure_parent_dir


HIGH_PERCENTILE_THRESHOLD = 0.67
LOW_PERCENTILE_THRESHOLD = 0.33
ROUTE_FOUNDATION_MIN_ROWS = 8
ROUTE_FOUNDATION_MIN_SUPPORT = 6
ROUTE_FOUNDATION_MIN_RATE = 0.65
ROUTE_FOUNDATION_MIN_AUTHORS = 2
CROSS_AUTHOR_TRANSFER_MIN_ROWS = 10
CROSS_AUTHOR_TRANSFER_MIN_SUPPORT = 8
CROSS_AUTHOR_TRANSFER_MIN_RATE = 0.70
CROSS_AUTHOR_TRANSFER_MIN_AUTHORS = 2
CROSS_AUTHOR_TRANSFER_MIN_AUTHOR_SUPPORT = 3
CROSS_AUTHOR_TRANSFER_MIN_AUTHOR_RATE = 0.55
FEATURE_FIELDS = (
    "style_family",
    "hook_type",
    "opening_problem_presence",
    "opening_payoff_presence",
    "cta_presence",
    "cta_type",
    "argument_shape",
)
EXAMPLE_MARKERS = ("比如", "例如", "举个例子", "就像", "拿", "一方面", "另一方面")
QUESTION_STYLE_MARKERS = ("为什么", "凭什么", "怎么", "谁", "哪一个", "难道")
CONTRARIAN_MARKERS = ("很多人以为", "不要以为", "你以为", "其实", "真相是", "恰恰相反")
PAYOFF_MARKERS = ("今天我们", "你会发现", "看懂", "答案", "结论", "只说一个核心")
PROBLEM_MARKERS = ("为什么", "问题", "危险", "失控", "压制", "焦虑", "崩", "困境", "误区")
STORY_MARKERS = ("那一年", "有一天", "当时", "后来", "故事")
AI_MARKERS = ("ai", "模型", "提示词", "agent", "人工智能", "大模型")
HISTORY_MARKERS = ("唐朝", "明朝", "晚唐", "太监", "皇帝", "王朝", "神策军", "安史之乱")
PHILOSOPHY_MARKERS = ("哲学", "存在", "意义", "尼采", "柏拉图", "苏格拉底", "康德")
COGNITION_MARKERS = ("认知", "思维", "注意力", "焦虑", "习惯", "脑", "心理")
BOOK_MARKERS = ("这本书", "作者", "书里", "读完", "章节", "书中")
POLITICS_MARKERS = ("制度", "权力", "政府", "政策", "国家机器", "统治")
BUSINESS_MARKERS = ("商业", "公司", "创业", "增长", "利润", "市场")
SCIENCE_MARKERS = ("科学", "实验", "物理", "化学", "生物", "研究")
LIST_COUNTDOWN_PATTERN = re.compile(
    r"(top\s*\d+|[一二三四五六七八九十两\d]+(?:个|点|条|层|种|步)(?:原因|误区|方法|问题|重点|困境|步骤|建议)|[一二三四五六七八九十两\d]+大(?:原因|误区|重点))",
    re.IGNORECASE,
)
ENUMERATION_MARKERS = ("第一", "第二", "第三", "第四", "首先", "其次", "最后")
COMPARISON_MARKERS = ("对比", "区别", "谁更", "哪个更", "孰优", "PK", "pk", "vs", "VS", "较量", "对决")


@dataclass(frozen=True)
class ParsedTranscript:
    metadata: dict[str, str]
    body: str

    @property
    def opening_excerpt(self) -> str:
        return _opening_excerpt(self.body)


@dataclass(frozen=True)
class Phase2AnalysisResult:
    labeled_rows: list[dict[str, str]]
    author_baselines: list[dict[str, str]]
    author_foundation_patterns: list[dict[str, str]]
    route_foundation_patterns: list[dict[str, str]]
    author_high_low: list[dict[str, str]]
    evidence_records: list[dict[str, str]]


ROW_LABEL_FIELDS = (
    "work_id",
    "author",
    "title",
    "txt_path",
    "content_type",
    "format",
    "domain",
    "primary_goal",
    "style_family",
    "hook_type",
    "opening_object_presence",
    "opening_problem_presence",
    "opening_payoff_presence",
    "argument_shape",
    "example_density_band",
    "cta_presence",
    "cta_type",
    "transcript_quality_gate",
    "manual_reviewed",
    "dedup_status",
    "char_count",
    "question_count",
    "opening_excerpt",
    "like_follower_ratio",
    "favorite_follower_ratio",
    "share_follower_ratio",
    "comment_follower_ratio",
    "composite_engagement_score_v1",
    "author_relative_percentile",
    "author_relative_band",
)
AUTHOR_BASELINE_FIELDS = (
    "author",
    "row_count",
    "composite_mean",
    "composite_median",
    "high_band_threshold",
    "low_band_threshold",
    "high_row_count",
    "mid_row_count",
    "low_row_count",
)
AUTHOR_FOUNDATION_FIELDS = (
    "author",
    "feature_name",
    "feature_value",
    "support_count",
    "author_row_count",
    "support_rate",
    "route_content_type",
    "route_format",
    "route_goal",
    "route_row_count",
    "route_rate",
    "foundation_gap",
    "confidence_grade",
)
ROUTE_FOUNDATION_FIELDS = (
    "route_content_type",
    "route_format",
    "route_goal",
    "row_count",
    "feature_name",
    "feature_value",
    "support_count",
    "route_rate",
)
AUTHOR_CONTRAST_FIELDS = (
    "author",
    "feature_name",
    "feature_value",
    "high_count",
    "low_count",
    "high_rate",
    "low_rate",
    "support_gap",
    "high_row_count",
    "low_row_count",
    "suggested_outcome",
)
EVIDENCE_RECORD_FIELDS = (
    "evidence_id",
    "evidence_kind",
    "evidence_origin",
    "evidence_polarity",
    "transfer_scope",
    "work_id",
    "author",
    "scope",
    "layer",
    "content_type",
    "format",
    "domain",
    "primary_goal",
    "style_family",
    "author_signature",
    "feature_name",
    "feature_value",
    "metric_name",
    "metric_value",
    "support_count",
    "contradiction_count",
    "support_prevalence",
    "contrast_prevalence",
    "baseline_prevalence",
    "support_sample_size",
    "contrast_sample_size",
    "baseline_sample_size",
    "route_content_type",
    "route_format",
    "route_goal",
    "confidence_grade",
    "ready_for_distillation",
    "source_excerpt",
    "evidence_refs",
    "notes",
)


def parse_standard_transcript(path: Path) -> ParsedTranscript:
    metadata, body = parse_transcript_header(path)
    return ParsedTranscript(metadata=metadata, body=body.strip())


def select_phase2_ready(
    rows: list[dict[str, str]],
    *,
    author: str = "",
    limit: int = 0,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    author_value = author.strip()
    for row in rows:
        if author_value and (row.get("author", "") or "").strip() != author_value:
            continue
        if (row.get("txt_sync_status", "") or "").strip() != "ok":
            continue
        if (row.get("dedup_status", "") or "").strip() == "unknown":
            continue
        if not (row.get("txt_path", "") or "").strip():
            continue
        selected.append(row)
        if limit > 0 and len(selected) >= limit:
            break
    return selected


def analyze_phase2_rows(
    rows: list[dict[str, str]],
    *,
    route_baseline_rows: list[dict[str, str]] | None = None,
) -> Phase2AnalysisResult:
    labeled_rows = [_build_labeled_row(row) for row in rows]
    ranked_rows, author_baselines = _attach_author_relative_metrics(labeled_rows)
    if route_baseline_rows is None or route_baseline_rows is rows:
        route_source_rows = ranked_rows
    else:
        route_source_rows = [_build_labeled_row(row) for row in route_baseline_rows]
    route_foundation_patterns = _build_route_foundation_patterns(route_source_rows)
    author_foundation_patterns = _build_author_foundation_patterns(
        ranked_rows,
        route_foundation_patterns=route_foundation_patterns,
    )
    author_high_low = _build_author_high_low_contrasts(ranked_rows)
    evidence_records = _build_evidence_records(
        author_high_low,
        ranked_rows,
        author_foundation_patterns=author_foundation_patterns,
        route_foundation_patterns=route_foundation_patterns,
        route_source_rows=route_source_rows,
    )
    return Phase2AnalysisResult(
        labeled_rows=ranked_rows,
        author_baselines=author_baselines,
        author_foundation_patterns=author_foundation_patterns,
        route_foundation_patterns=route_foundation_patterns,
        author_high_low=author_high_low,
        evidence_records=evidence_records,
    )


def write_phase2_exports(
    result: Phase2AnalysisResult,
    analysis_dir: Path,
    *,
    target_authors: tuple[str, ...] | None = None,
) -> dict[str, Path]:
    labels_path = analysis_dir / "labels" / "row_labels.csv"
    baselines_path = analysis_dir / "baselines" / "author_baselines.csv"
    author_foundations_path = analysis_dir / "baselines" / "author_foundation_patterns.csv"
    route_foundations_path = analysis_dir / "baselines" / "route_foundation_patterns.csv"
    contrasts_path = analysis_dir / "contrasts" / "author_high_low.csv"
    evidence_path = analysis_dir / "evidence" / "evidence_records.csv"

    effective_target_authors, replace_all = _resolve_target_authors(
        explicit_target_authors=target_authors,
        inferred_target_authors=_target_authors_from_phase2_result(result),
    )
    _merge_rows(
        labels_path,
        result.labeled_rows,
        key_fields=("work_id",),
        target_authors=effective_target_authors,
        replace_all=replace_all,
        empty_fieldnames=ROW_LABEL_FIELDS,
    )
    _merge_rows(
        baselines_path,
        result.author_baselines,
        key_fields=("author",),
        target_authors=effective_target_authors,
        replace_all=replace_all,
        empty_fieldnames=AUTHOR_BASELINE_FIELDS,
    )
    _merge_rows(
        author_foundations_path,
        result.author_foundation_patterns,
        key_fields=("author", "feature_name", "feature_value", "route_content_type", "route_format", "route_goal"),
        target_authors=effective_target_authors,
        replace_all=replace_all,
        empty_fieldnames=AUTHOR_FOUNDATION_FIELDS,
    )
    _merge_rows(
        route_foundations_path,
        result.route_foundation_patterns,
        key_fields=("route_content_type", "route_format", "route_goal", "feature_name", "feature_value"),
        target_authors=(),
        replace_all=True,
        empty_fieldnames=ROUTE_FOUNDATION_FIELDS,
    )
    _merge_rows(
        contrasts_path,
        result.author_high_low,
        key_fields=("author", "feature_name", "feature_value"),
        target_authors=effective_target_authors,
        replace_all=replace_all,
        empty_fieldnames=AUTHOR_CONTRAST_FIELDS,
    )
    _merge_rows(
        evidence_path,
        result.evidence_records,
        key_fields=("evidence_id",),
        target_authors=effective_target_authors,
        replace_all=replace_all,
        empty_fieldnames=EVIDENCE_RECORD_FIELDS,
    )

    return {
        "labels": labels_path,
        "baselines": baselines_path,
        "author_foundations": author_foundations_path,
        "route_foundations": route_foundations_path,
        "contrasts": contrasts_path,
        "evidence": evidence_path,
    }


def _build_labeled_row(row: dict[str, str]) -> dict[str, str]:
    txt_path = Path((row.get("txt_path", "") or "").strip())
    parsed = parse_standard_transcript(txt_path)
    body = parsed.body
    title = (row.get("title", "") or "").strip()
    full_text = f"{title}\n{body}".strip()
    opening = parsed.opening_excerpt
    char_count = compact_char_count(body)
    question_count = count_question_marks(body)
    duration_seconds = _to_float(row.get("duration_seconds"))

    domain = _infer_domain(full_text)
    format_name = _infer_format(
        full_text,
        char_count=char_count,
        duration_seconds=duration_seconds,
        early_text=f"{title}\n{opening}".strip(),
    )
    content_type = _infer_content_type(full_text, domain=domain)
    style_family = _infer_style_family(opening, body=body, char_count=char_count, question_count=question_count)
    hook_type = _infer_hook_type(opening, style_family=style_family)
    cta_presence, cta_type = _infer_cta(body)
    ratios = _engagement_ratios(row)

    return {
        "work_id": (row.get("work_id", "") or "").strip(),
        "author": (row.get("author", "") or "").strip(),
        "title": title,
        "txt_path": str(txt_path),
        "content_type": content_type,
        "format": format_name,
        "domain": domain,
        "primary_goal": _infer_primary_goal(cta_type=cta_type, content_type=content_type),
        "style_family": style_family,
        "hook_type": hook_type,
        "opening_object_presence": "yes" if compact_char_count(opening) >= 8 else "no",
        "opening_problem_presence": "yes" if _contains_any(opening, PROBLEM_MARKERS) or "？" in opening or "?" in opening else "no",
        "opening_payoff_presence": "yes" if _contains_any(opening, PAYOFF_MARKERS) else "no",
        "argument_shape": _infer_argument_shape(body),
        "example_density_band": _infer_example_density_band(body),
        "cta_presence": cta_presence,
        "cta_type": cta_type,
        "transcript_quality_gate": _infer_transcript_quality_gate(row),
        "manual_reviewed": (row.get("manual_reviewed", "") or "").strip() or "no",
        "dedup_status": (row.get("dedup_status", "") or "").strip(),
        "char_count": str(char_count),
        "question_count": str(question_count),
        "opening_excerpt": opening,
        "like_follower_ratio": _fmt_float(ratios["like_follower_ratio"]),
        "favorite_follower_ratio": _fmt_float(ratios["favorite_follower_ratio"]),
        "share_follower_ratio": _fmt_float(ratios["share_follower_ratio"]),
        "comment_follower_ratio": _fmt_float(ratios["comment_follower_ratio"]),
        "composite_engagement_score_v1": _fmt_float(ratios["composite_engagement_score_v1"]),
        "author_relative_percentile": "",
        "author_relative_band": "",
    }


def _attach_author_relative_metrics(
    labeled_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows_by_author: dict[str, list[dict[str, str]]] = {}
    for row in labeled_rows:
        rows_by_author.setdefault(row["author"], []).append(row)

    ranked_rows: list[dict[str, str]] = []
    baselines: list[dict[str, str]] = []
    for author, author_rows in rows_by_author.items():
        scored = sorted(
            author_rows,
            key=lambda row: (_to_float(row.get("composite_engagement_score_v1")), row["work_id"]),
        )
        total = len(scored)
        enriched_rows: list[dict[str, str]] = []
        scores = [_to_float(row.get("composite_engagement_score_v1")) for row in scored]
        high_count = 0
        low_count = 0
        mid_count = 0
        for index, row in enumerate(scored):
            percentile = 0.5 if total <= 1 else index / max(1, total - 1)
            band = _percentile_band(percentile)
            if band == "high":
                high_count += 1
            elif band == "low":
                low_count += 1
            else:
                mid_count += 1
            enriched = dict(row)
            enriched["author_relative_percentile"] = _fmt_float(percentile)
            enriched["author_relative_band"] = band
            enriched_rows.append(enriched)
        ranked_rows.extend(sorted(enriched_rows, key=lambda row: row["work_id"]))
        baselines.append(
            {
                "author": author,
                "row_count": str(total),
                "composite_mean": _fmt_float(mean(scores) if scores else 0.0),
                "composite_median": _fmt_float(median(scores) if scores else 0.0),
                "high_band_threshold": _fmt_float(HIGH_PERCENTILE_THRESHOLD),
                "low_band_threshold": _fmt_float(LOW_PERCENTILE_THRESHOLD),
                "high_row_count": str(high_count),
                "mid_row_count": str(mid_count),
                "low_row_count": str(low_count),
            }
        )
    return sorted(ranked_rows, key=lambda row: (row["author"], row["work_id"])), sorted(
        baselines,
        key=lambda row: row["author"],
    )


def _build_author_high_low_contrasts(labeled_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows_by_author: dict[str, list[dict[str, str]]] = {}
    for row in labeled_rows:
        rows_by_author.setdefault(row["author"], []).append(row)

    contrasts: list[dict[str, str]] = []
    for author, author_rows in rows_by_author.items():
        high_rows = [row for row in author_rows if row.get("author_relative_band") == "high"]
        low_rows = [row for row in author_rows if row.get("author_relative_band") == "low"]
        if not high_rows or not low_rows:
            continue
        for feature_name in FEATURE_FIELDS:
            values = sorted({row.get(feature_name, "") or "" for row in high_rows + low_rows})
            for value in values:
                if not value:
                    continue
                high_count = sum(1 for row in high_rows if row.get(feature_name) == value)
                low_count = sum(1 for row in low_rows if row.get(feature_name) == value)
                high_rate = high_count / len(high_rows)
                low_rate = low_count / len(low_rows)
                gap = high_rate - low_rate
                contrasts.append(
                    {
                        "author": author,
                        "feature_name": feature_name,
                        "feature_value": value,
                        "high_count": str(high_count),
                        "low_count": str(low_count),
                        "high_rate": _fmt_float(high_rate),
                        "low_rate": _fmt_float(low_rate),
                        "support_gap": _fmt_float(gap),
                        "high_row_count": str(len(high_rows)),
                        "low_row_count": str(len(low_rows)),
                        "suggested_outcome": _suggested_outcome(gap),
                    }
                )
    return contrasts


def _build_route_foundation_patterns(labeled_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows_by_route: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in labeled_rows:
        rows_by_route.setdefault(_route_scope(row), []).append(row)

    patterns: list[dict[str, str]] = []
    for route_scope, route_rows in rows_by_route.items():
        route_content_type, route_format, route_goal = route_scope
        row_count = len(route_rows)
        for feature_name in FEATURE_FIELDS:
            values = sorted({(row.get(feature_name, "") or "").strip() for row in route_rows if (row.get(feature_name, "") or "").strip()})
            for value in values:
                support_count = sum(1 for row in route_rows if (row.get(feature_name, "") or "").strip() == value)
                route_rate = support_count / row_count if row_count else 0.0
                patterns.append(
                    {
                        "route_content_type": route_content_type,
                        "route_format": route_format,
                        "route_goal": route_goal,
                        "row_count": str(row_count),
                        "feature_name": feature_name,
                        "feature_value": value,
                        "support_count": str(support_count),
                        "route_rate": _fmt_float(route_rate),
                    }
                )
    return sorted(
        patterns,
        key=lambda row: (
            row["route_content_type"],
            row["route_format"],
            row["route_goal"],
            row["feature_name"],
            row["feature_value"],
        ),
    )


def _build_author_foundation_patterns(
    labeled_rows: list[dict[str, str]],
    *,
    route_foundation_patterns: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows_by_author: dict[str, list[dict[str, str]]] = {}
    for row in labeled_rows:
        rows_by_author.setdefault(row["author"], []).append(row)

    route_index = {
        (
            row["route_content_type"],
            row["route_format"],
            row["route_goal"],
            row["feature_name"],
            row["feature_value"],
        ): row
        for row in route_foundation_patterns
    }

    patterns: list[dict[str, str]] = []
    for author, author_rows in rows_by_author.items():
        if len(author_rows) < 4:
            continue
        rows_by_route: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        for row in author_rows:
            rows_by_route.setdefault(_route_scope(row), []).append(row)

        for route_scope, scoped_rows in rows_by_route.items():
            author_scope_row_count = len(scoped_rows)
            if author_scope_row_count < 6:
                continue
            for feature_name in FEATURE_FIELDS:
                values = sorted(
                    {
                        (row.get(feature_name, "") or "").strip()
                        for row in scoped_rows
                        if (row.get(feature_name, "") or "").strip()
                    }
                )
                for value in values:
                    support_rows = [row for row in scoped_rows if (row.get(feature_name, "") or "").strip() == value]
                    support_count = len(support_rows)
                    support_rate = support_count / author_scope_row_count if author_scope_row_count else 0.0
                    if support_count < 4 or support_rate < 0.55:
                        continue

                    route_row = route_index.get((*route_scope, feature_name, value))
                    baseline_row_count = 0
                    baseline_rate = 0.0
                    foundation_gap = support_rate
                    if route_row is not None:
                        total_route_row_count = _to_int(route_row.get("row_count"))
                        total_route_support_count = _to_int(route_row.get("support_count"))
                        external_row_count = max(0, total_route_row_count - author_scope_row_count)
                        external_support_count = max(0, total_route_support_count - support_count)
                        if external_row_count >= 6:
                            baseline_row_count = external_row_count
                            baseline_rate = external_support_count / external_row_count
                            foundation_gap = support_rate - baseline_rate

                    if baseline_row_count > 0:
                        if foundation_gap < 0.15:
                            continue
                    elif support_rate < 0.65:
                        continue

                    confidence_grade = _foundation_confidence_grade(
                        support_rate=support_rate,
                        foundation_gap=foundation_gap,
                        route_row_count=baseline_row_count,
                    )
                    patterns.append(
                        {
                            "author": author,
                            "feature_name": feature_name,
                            "feature_value": value,
                            "support_count": str(support_count),
                            "author_row_count": str(author_scope_row_count),
                            "support_rate": _fmt_float(support_rate),
                            "route_content_type": route_scope[0],
                            "route_format": route_scope[1],
                            "route_goal": route_scope[2],
                            "route_row_count": str(baseline_row_count),
                            "route_rate": _fmt_float(baseline_rate),
                            "foundation_gap": _fmt_float(foundation_gap),
                            "confidence_grade": confidence_grade,
                        }
                    )
    return sorted(
        patterns,
        key=lambda row: (
            row["author"],
            row["route_content_type"],
            row["route_format"],
            row["route_goal"],
            row["feature_name"],
            row["feature_value"],
        ),
    )


def _build_route_foundation_evidence(
    route_foundation_patterns: list[dict[str, str]],
    route_source_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    evidence_records: list[dict[str, str]] = []
    for pattern in route_foundation_patterns:
        row_count = _to_int(pattern.get("row_count"))
        support_count = _to_int(pattern.get("support_count"))
        route_rate = _to_float(pattern.get("route_rate"))
        if row_count < ROUTE_FOUNDATION_MIN_ROWS:
            continue
        if support_count < ROUTE_FOUNDATION_MIN_SUPPORT or route_rate < ROUTE_FOUNDATION_MIN_RATE:
            continue

        route_scope = (
            pattern["route_content_type"],
            pattern["route_format"],
            pattern["route_goal"],
        )
        support_rows = _support_rows_for_pattern(
            route_source_rows,
            route_scope=route_scope,
            feature_name=pattern["feature_name"],
            feature_value=pattern["feature_value"],
        )
        author_count = len({row["author"] for row in support_rows if row.get("author")})
        if author_count < ROUTE_FOUNDATION_MIN_AUTHORS:
            continue

        confidence_grade = _route_foundation_confidence_grade(
            row_count=row_count,
            support_count=support_count,
            support_rate=route_rate,
            author_count=author_count,
        )
        evidence_records.append(
            {
                "evidence_id": _hashed_id(
                    "ev",
                    pattern["route_content_type"],
                    pattern["route_format"],
                    pattern["route_goal"],
                    pattern["feature_name"],
                    pattern["feature_value"],
                    "route_foundation_pattern",
                ),
                "evidence_kind": "route_foundation_pattern",
                "evidence_origin": "route",
                "evidence_polarity": "positive",
                "transfer_scope": "route_local",
                "work_id": "",
                "author": "多作者",
                "scope": "same_content_type",
                "layer": _evidence_layer_for_feature(pattern["feature_name"]),
                "content_type": pattern["route_content_type"],
                "format": pattern["route_format"],
                "domain": _dominant_domain(support_rows),
                "primary_goal": pattern["route_goal"],
                "style_family": _dominant_style_family(support_rows),
                "author_signature": "",
                "feature_name": pattern["feature_name"],
                "feature_value": pattern["feature_value"],
                "metric_name": "route_prevalence",
                "metric_value": pattern["route_rate"],
                "support_count": pattern["support_count"],
                "contradiction_count": str(max(0, row_count - support_count)),
                "support_prevalence": pattern["route_rate"],
                "contrast_prevalence": _fmt_float(1.0 - route_rate),
                "baseline_prevalence": "",
                "support_sample_size": pattern["row_count"],
                "contrast_sample_size": "",
                "baseline_sample_size": "",
                "route_content_type": pattern["route_content_type"],
                "route_format": pattern["route_format"],
                "route_goal": pattern["route_goal"],
                "confidence_grade": confidence_grade,
                "ready_for_distillation": "yes" if confidence_grade in {"E2", "E3", "E4"} else "no",
                "source_excerpt": support_rows[0]["opening_excerpt"] if support_rows else "",
                "evidence_refs": "|".join(row["work_id"] for row in support_rows[:5]),
                "notes": _build_route_foundation_evidence_note(pattern, author_count=author_count),
            }
        )
    return evidence_records


def _build_cross_author_transfer_evidence(
    route_foundation_patterns: list[dict[str, str]],
    route_source_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    evidence_records: list[dict[str, str]] = []
    for pattern in route_foundation_patterns:
        row_count = _to_int(pattern.get("row_count"))
        support_count = _to_int(pattern.get("support_count"))
        route_rate = _to_float(pattern.get("route_rate"))
        if row_count < CROSS_AUTHOR_TRANSFER_MIN_ROWS:
            continue
        if support_count < CROSS_AUTHOR_TRANSFER_MIN_SUPPORT or route_rate < CROSS_AUTHOR_TRANSFER_MIN_RATE:
            continue

        route_scope = (
            pattern["route_content_type"],
            pattern["route_format"],
            pattern["route_goal"],
        )
        route_rows = [row for row in route_source_rows if _route_scope(row) == route_scope]
        author_stats = _author_support_stats(
            route_rows,
            feature_name=pattern["feature_name"],
            feature_value=pattern["feature_value"],
        )
        supporting_authors = [
            author
            for author, stats in author_stats.items()
            if stats["support_count"] >= CROSS_AUTHOR_TRANSFER_MIN_AUTHOR_SUPPORT
            and stats["support_rate"] >= CROSS_AUTHOR_TRANSFER_MIN_AUTHOR_RATE
        ]
        if len(supporting_authors) < CROSS_AUTHOR_TRANSFER_MIN_AUTHORS:
            continue

        support_rows = _support_rows_for_pattern(
            route_source_rows,
            route_scope=route_scope,
            feature_name=pattern["feature_name"],
            feature_value=pattern["feature_value"],
        )
        confidence_grade = _cross_author_transfer_confidence_grade(
            row_count=row_count,
            support_count=support_count,
            support_rate=route_rate,
            author_count=len(supporting_authors),
        )
        evidence_records.append(
            {
                "evidence_id": _hashed_id(
                    "ev",
                    pattern["route_content_type"],
                    pattern["route_format"],
                    pattern["route_goal"],
                    pattern["feature_name"],
                    pattern["feature_value"],
                    "cross_author_transfer_pattern",
                ),
                "evidence_kind": "cross_author_transfer_pattern",
                "evidence_origin": "transfer",
                "evidence_polarity": "positive",
                "transfer_scope": "cross_author",
                "work_id": "",
                "author": "多作者",
                "scope": "cross_author",
                "layer": _evidence_layer_for_feature(pattern["feature_name"]),
                "content_type": pattern["route_content_type"],
                "format": pattern["route_format"],
                "domain": _dominant_domain(support_rows),
                "primary_goal": pattern["route_goal"],
                "style_family": _dominant_style_family(support_rows),
                "author_signature": "",
                "feature_name": pattern["feature_name"],
                "feature_value": pattern["feature_value"],
                "metric_name": "cross_author_route_prevalence",
                "metric_value": pattern["route_rate"],
                "support_count": pattern["support_count"],
                "contradiction_count": str(max(0, row_count - support_count)),
                "support_prevalence": pattern["route_rate"],
                "contrast_prevalence": _fmt_float(1.0 - route_rate),
                "baseline_prevalence": "",
                "support_sample_size": pattern["row_count"],
                "contrast_sample_size": "",
                "baseline_sample_size": "",
                "route_content_type": pattern["route_content_type"],
                "route_format": pattern["route_format"],
                "route_goal": pattern["route_goal"],
                "confidence_grade": confidence_grade,
                "ready_for_distillation": "yes" if confidence_grade in {"E2", "E3", "E4"} else "no",
                "source_excerpt": support_rows[0]["opening_excerpt"] if support_rows else "",
                "evidence_refs": "|".join(row["work_id"] for row in support_rows[:5]),
                "notes": _build_cross_author_transfer_evidence_note(pattern, supporting_authors=supporting_authors),
            }
        )
    return evidence_records


def _build_evidence_records(
    contrasts: list[dict[str, str]],
    labeled_rows: list[dict[str, str]],
    *,
    author_foundation_patterns: list[dict[str, str]],
    route_foundation_patterns: list[dict[str, str]],
    route_source_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows_by_author: dict[str, list[dict[str, str]]] = {}
    for row in labeled_rows:
        rows_by_author.setdefault(row["author"], []).append(row)

    evidence_records: list[dict[str, str]] = [
        *_build_route_foundation_evidence(route_foundation_patterns, route_source_rows),
        *_build_cross_author_transfer_evidence(route_foundation_patterns, route_source_rows),
    ]
    for foundation in author_foundation_patterns:
        author = foundation["author"]
        feature_name = foundation["feature_name"]
        feature_value = foundation["feature_value"]
        route_scope = (
            foundation["route_content_type"],
            foundation["route_format"],
            foundation["route_goal"],
        )
        support_rows = [
            row
            for row in rows_by_author.get(author, [])
            if (row.get(feature_name, "") or "").strip() == feature_value and _route_scope(row) == route_scope
        ]
        refs = "|".join(row["work_id"] for row in support_rows[:5])
        source_excerpt = support_rows[0]["opening_excerpt"] if support_rows else ""
        confidence_grade = foundation["confidence_grade"]
        evidence_records.append(
            {
                "evidence_id": _hashed_id(
                    "ev",
                    author,
                    foundation["route_content_type"],
                    foundation["route_format"],
                    foundation["route_goal"],
                    feature_name,
                    feature_value,
                    "author_foundation_pattern",
                ),
                "evidence_kind": "author_foundation_pattern",
                "evidence_origin": "foundation",
                "evidence_polarity": "positive",
                "transfer_scope": "author_local",
                "work_id": "",
                "author": author,
                "scope": "same_author",
                "layer": _evidence_layer_for_feature(feature_name),
                "content_type": foundation["route_content_type"],
                "format": foundation["route_format"],
                "domain": _dominant_domain(support_rows),
                "primary_goal": foundation["route_goal"],
                "style_family": _dominant_style_family(support_rows),
                "author_signature": "",
                "feature_name": feature_name,
                "feature_value": feature_value,
                "metric_name": "author_route_prevalence_gap",
                "metric_value": foundation["foundation_gap"],
                "support_count": foundation["support_count"],
                "contradiction_count": str(max(0, _to_int(foundation["author_row_count"]) - _to_int(foundation["support_count"]))),
                "support_prevalence": foundation["support_rate"],
                "contrast_prevalence": "",
                "baseline_prevalence": foundation["route_rate"],
                "support_sample_size": foundation["author_row_count"],
                "contrast_sample_size": "",
                "baseline_sample_size": foundation["route_row_count"],
                "route_content_type": foundation["route_content_type"],
                "route_format": foundation["route_format"],
                "route_goal": foundation["route_goal"],
                "confidence_grade": confidence_grade,
                "ready_for_distillation": "yes" if confidence_grade in {"E2", "E3", "E4"} else "no",
                "source_excerpt": source_excerpt,
                "evidence_refs": refs,
                "notes": _build_foundation_evidence_note(foundation),
            }
        )

    for contrast in contrasts:
        gap = _to_float(contrast.get("support_gap"))
        if abs(gap) < 0.15:
            continue
        author = contrast["author"]
        feature_name = contrast["feature_name"]
        feature_value = contrast["feature_value"]
        support_is_high = gap > 0
        support_count = int(contrast["high_count"] if support_is_high else contrast["low_count"])
        contradiction_count = int(contrast["low_count"] if support_is_high else contrast["high_count"])
        if abs(gap) >= 0.2:
            confidence_grade = "E2"
            ready = "yes"
            kind = "differential_gain_pattern" if support_is_high else "negative_pattern"
        else:
            confidence_grade = "E1"
            ready = "no"
            kind = "contrast_finding"
        support_rows = [
            row
            for row in rows_by_author.get(author, [])
            if row.get("author_relative_band") == ("high" if support_is_high else "low")
            and row.get(feature_name) == feature_value
        ]
        refs = "|".join(row["work_id"] for row in support_rows[:5])
        source_excerpt = support_rows[0]["opening_excerpt"] if support_rows else ""
        evidence_records.append(
            {
                "evidence_id": _hashed_id("ev", author, feature_name, feature_value, kind),
                "evidence_kind": kind,
                "evidence_origin": "differential",
                "evidence_polarity": "positive" if support_is_high else "negative",
                "transfer_scope": "author_local",
                "work_id": support_rows[0]["work_id"] if len(support_rows) == 1 else "",
                "author": author,
                "scope": "same_author",
                "layer": _evidence_layer_for_feature(feature_name),
                "content_type": support_rows[0]["content_type"] if support_rows else "",
                "format": support_rows[0]["format"] if support_rows else "",
                "domain": support_rows[0]["domain"] if support_rows else "",
                "primary_goal": support_rows[0]["primary_goal"] if support_rows else "",
                "style_family": support_rows[0]["style_family"] if support_rows else "",
                "author_signature": "",
                "feature_name": feature_name,
                "feature_value": feature_value,
                "metric_name": "high_low_rate_gap",
                "metric_value": _fmt_float(gap),
                "support_count": str(support_count),
                "contradiction_count": str(contradiction_count),
                "support_prevalence": contrast["high_rate"] if support_is_high else contrast["low_rate"],
                "contrast_prevalence": contrast["low_rate"] if support_is_high else contrast["high_rate"],
                "baseline_prevalence": "",
                "support_sample_size": contrast["high_row_count"] if support_is_high else contrast["low_row_count"],
                "contrast_sample_size": contrast["low_row_count"] if support_is_high else contrast["high_row_count"],
                "baseline_sample_size": "",
                "route_content_type": support_rows[0]["content_type"] if support_rows else "",
                "route_format": support_rows[0]["format"] if support_rows else "",
                "route_goal": support_rows[0]["primary_goal"] if support_rows else "",
                "confidence_grade": confidence_grade,
                "ready_for_distillation": ready,
                "source_excerpt": source_excerpt,
                "evidence_refs": refs,
                "notes": _build_evidence_note(contrast, kind=kind),
            }
        )
    return evidence_records


def _merge_rows(
    path: Path,
    new_rows: list[dict[str, str]],
    *,
    key_fields: tuple[str, ...],
    target_authors: tuple[str, ...],
    replace_all: bool,
    empty_fieldnames: tuple[str, ...],
) -> None:
    existing_rows = read_csv_rows(path) if path.exists() else []
    retained_rows = [] if replace_all else [
        row
        for row in existing_rows
        if not target_authors or (row.get("author", "") or "").strip() not in target_authors
    ]
    merged_by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for row in retained_rows + new_rows:
        merged_by_key[_row_key(row, key_fields)] = row
    merged_rows = list(merged_by_key.values())
    ensure_parent_dir(path)
    if not merged_rows:
        write_csv_rows(path, list(empty_fieldnames), [])
        return
    fieldnames = _merged_fieldnames(retained_rows, new_rows) or list(empty_fieldnames)
    sorted_rows = sorted(merged_rows, key=lambda row: _row_key(row, ("author", *key_fields)))
    write_csv_rows(path, fieldnames, sorted_rows)


def _row_key(row: dict[str, str], key_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple((row.get(field, "") or "").strip() for field in key_fields)


def _target_authors_from_phase2_result(result: Phase2AnalysisResult) -> tuple[str, ...]:
    authors = {(_row.get("author", "") or "").strip() for _row in result.labeled_rows if (_row.get("author", "") or "").strip()}
    authors.update(
        (_row.get("author", "") or "").strip()
        for _row in result.author_foundation_patterns
        if (_row.get("author", "") or "").strip()
    )
    authors.update(
        (_row.get("author", "") or "").strip()
        for _row in result.author_high_low
        if (_row.get("author", "") or "").strip()
    )
    authors.update(
        (_row.get("author", "") or "").strip()
        for _row in result.evidence_records
        if (_row.get("author", "") or "").strip()
    )
    authors.update(
        (_row.get("author", "") or "").strip()
        for _row in result.author_baselines
        if (_row.get("author", "") or "").strip()
    )
    return tuple(sorted(authors))


def _merged_fieldnames(existing_rows: list[dict[str, str]], new_rows: list[dict[str, str]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in [*new_rows, *existing_rows]:
        for field in row.keys():
            if field in seen:
                continue
            seen.add(field)
            fieldnames.append(field)
    return fieldnames


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


def _infer_domain(text: str) -> str:
    lowered = text.lower()
    checks = [
        ("ai", AI_MARKERS),
        ("history", HISTORY_MARKERS),
        ("philosophy", PHILOSOPHY_MARKERS),
        ("cognition", COGNITION_MARKERS),
        ("books", BOOK_MARKERS),
        ("politics", POLITICS_MARKERS),
        ("business", BUSINESS_MARKERS),
        ("science", SCIENCE_MARKERS),
    ]
    for name, markers in checks:
        if _contains_any(lowered, tuple(marker.lower() for marker in markers)):
            return name
    return "books" if "书" in text else "cognition"


def _infer_format(text: str, *, char_count: int, duration_seconds: float, early_text: str = "") -> str:
    signal_text = (early_text or text).strip()
    lowered = signal_text.lower()
    if any(marker in lowered for marker in ("vs", "pk", "对决", "较量", "谁更")):
        return "debate_showdown"
    if (
        "清单" in signal_text
        or LIST_COUNTDOWN_PATTERN.search(signal_text)
        or _count_markers(signal_text, ENUMERATION_MARKERS) >= 2
    ):
        return "list_countdown"
    if duration_seconds >= 150 or char_count >= 280:
        return "long_explainer"
    return "short_monologue"


def _infer_content_type(text: str, *, domain: str) -> str:
    if _contains_any(text, COMPARISON_MARKERS):
        return "comparison_review"
    if _contains_any(text, BOOK_MARKERS):
        return "book_digest"
    if _contains_any(text, ("怎么做", "步骤", "方法", "记住", "操作")):
        return "method_walkthrough"
    if domain == "history" and _contains_any(text, ("为什么", "原因", "失控", "转折", "制度")):
        return "historical_interpretation"
    return "concept_explainer"


def _infer_style_family(opening: str, *, body: str, char_count: int, question_count: int) -> str:
    if "？" in opening or "?" in opening or _contains_any(opening, QUESTION_STYLE_MARKERS):
        return "question_hook"
    if _contains_any(opening, STORY_MARKERS):
        return "story_led"
    if _contains_any(opening, CONTRARIAN_MARKERS):
        return "contrarian_reframe"
    if char_count >= 320 and question_count <= 1:
        return "one_breath_deep_dive"
    if _contains_any(opening, ("必须", "一定", "根本", "核心")):
        return "strong_claim"
    return "cold_explainer"


def _infer_hook_type(opening: str, *, style_family: str) -> str:
    if style_family == "question_hook":
        return "question"
    if style_family in {"strong_claim", "contrarian_reframe"}:
        return "claim"
    if style_family == "story_led":
        return "scene"
    return "statement"


def _infer_argument_shape(body: str) -> str:
    if "先" in body and ("再" in body or "然后" in body) and "最后" in body:
        return "stepwise_explainer"
    if _contains_any(body, ("一方面", "另一方面", "对比", "反过来")):
        return "contrastive_argument"
    if _contains_any(body, ("比如", "例如", "举个例子")):
        return "example_led"
    return "straight_explainer"


def _infer_example_density_band(body: str) -> str:
    count = sum(body.count(marker) for marker in EXAMPLE_MARKERS)
    if count >= 2:
        return "high"
    if count == 1:
        return "medium"
    return "low"


def _infer_cta(body: str) -> tuple[str, str]:
    tail = body[-120:]
    if "关注" in tail:
        return "yes", "follow"
    if "收藏" in tail:
        return "yes", "save"
    if "评论" in tail or "留言" in tail:
        return "yes", "interaction"
    if "点赞" in tail or "转发" in tail:
        return "yes", "interaction"
    return "no", "none"


def _infer_primary_goal(*, cta_type: str, content_type: str) -> str:
    if cta_type == "follow":
        return "follow"
    if cta_type == "save" or content_type in {"book_digest", "method_walkthrough"}:
        return "save"
    if cta_type == "interaction":
        return "interaction"
    return "completion"


def _infer_transcript_quality_gate(row: dict[str, str]) -> str:
    if (row.get("manual_reviewed", "") or "").strip() == "yes":
        return "human_reviewed"
    grade = (row.get("asr_quality_grade", "") or "").strip().upper()
    if grade in {"A", "B"}:
        return "pass"
    if grade == "C":
        return "review"
    return "fail"


def _engagement_ratios(row: dict[str, str]) -> dict[str, float]:
    followers = _to_float(row.get("followers"))
    likes = _to_float(row.get("likes"))
    comments = _to_float(row.get("comments"))
    favorites = _to_float(row.get("favorites"))
    shares = _to_float(row.get("shares"))
    if followers <= 0:
        return {
            "like_follower_ratio": 0.0,
            "comment_follower_ratio": 0.0,
            "favorite_follower_ratio": 0.0,
            "share_follower_ratio": 0.0,
            "composite_engagement_score_v1": 0.0,
        }
    like_ratio = likes / followers
    comment_ratio = comments / followers
    favorite_ratio = favorites / followers
    share_ratio = shares / followers
    composite = 0.5 * like_ratio + 0.3 * favorite_ratio + 0.2 * share_ratio
    return {
        "like_follower_ratio": like_ratio,
        "comment_follower_ratio": comment_ratio,
        "favorite_follower_ratio": favorite_ratio,
        "share_follower_ratio": share_ratio,
        "composite_engagement_score_v1": composite,
    }


def _percentile_band(percentile: float) -> str:
    if percentile >= HIGH_PERCENTILE_THRESHOLD:
        return "high"
    if percentile <= LOW_PERCENTILE_THRESHOLD:
        return "low"
    return "mid"


def _suggested_outcome(gap: float) -> str:
    if gap >= 0.5:
        return "positive_pattern"
    if gap <= -0.5:
        return "negative_pattern"
    return "mixed"


def _evidence_layer_for_feature(feature_name: str) -> str:
    if feature_name == "style_family":
        return "style_family"
    return "general"


def _build_evidence_note(contrast: dict[str, str], *, kind: str) -> str:
    direction = "high performers" if kind == "differential_gain_pattern" else "low performers"
    return (
        f"Within-author contrast: {contrast['feature_name']}={contrast['feature_value']} appears more often in "
        f"{direction}. gap={contrast['support_gap']}"
    )


def _build_foundation_evidence_note(foundation: dict[str, str]) -> str:
    route_row_count = _to_int(foundation.get("route_row_count"))
    if route_row_count <= 0:
        return (
            "Author foundation: "
            f"{foundation['feature_name']}={foundation['feature_value']} stays common inside this author's matched route. "
            "Current baseline support is author-local only."
        )
    return (
        "Author foundation: "
        f"{foundation['feature_name']}={foundation['feature_value']} stays common inside this author's matched route "
        f"and exceeds the external route baseline. gap={foundation['foundation_gap']}"
    )


def _build_route_foundation_evidence_note(pattern: dict[str, str], *, author_count: int) -> str:
    return (
        "Route foundation: "
        f"{pattern['feature_name']}={pattern['feature_value']} is common inside route "
        f"{pattern['route_content_type']}/{pattern['route_format']}/{pattern['route_goal']}. "
        f"support_rate={pattern['route_rate']}; supporting_authors={author_count}"
    )


def _build_cross_author_transfer_evidence_note(pattern: dict[str, str], *, supporting_authors: list[str]) -> str:
    return (
        "Cross-author transfer: "
        f"{pattern['feature_name']}={pattern['feature_value']} repeats across authors inside route "
        f"{pattern['route_content_type']}/{pattern['route_format']}/{pattern['route_goal']}. "
        f"supporting_authors={','.join(sorted(supporting_authors))}"
    )


def _route_scope(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        (row.get("content_type", "") or "").strip() or "unknown",
        (row.get("format", "") or "").strip() or "unknown",
        (row.get("primary_goal", "") or "").strip() or "unknown",
    )


def _dominant_route_scope(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    counts: dict[tuple[str, str, str], int] = {}
    for row in rows:
        scope = _route_scope(row)
        counts[scope] = counts.get(scope, 0) + 1
    if not counts:
        return ("unknown", "unknown", "unknown")
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _dominant_domain(rows: list[dict[str, str]]) -> str:
    return _dominant_text_value(rows, "domain")


def _dominant_style_family(rows: list[dict[str, str]]) -> str:
    return _dominant_text_value(rows, "style_family")


def _dominant_text_value(rows: list[dict[str, str]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        value = (row.get(field, "") or "").strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _foundation_confidence_grade(*, support_rate: float, foundation_gap: float, route_row_count: int) -> str:
    if route_row_count <= 0:
        if support_rate >= 0.65:
            return "E2"
        return "E1"
    if support_rate >= 0.7 and foundation_gap >= 0.25 and route_row_count >= 10:
        return "E3"
    if support_rate >= 0.55 and foundation_gap >= 0.15 and route_row_count >= 6:
        return "E2"
    return "E1"


def _route_foundation_confidence_grade(
    *,
    row_count: int,
    support_count: int,
    support_rate: float,
    author_count: int,
) -> str:
    if author_count >= 3 and row_count >= 16 and support_count >= 12 and support_rate >= 0.75:
        return "E4"
    if author_count >= 2 and row_count >= ROUTE_FOUNDATION_MIN_ROWS and support_rate >= ROUTE_FOUNDATION_MIN_RATE:
        return "E3"
    return "E1"


def _cross_author_transfer_confidence_grade(
    *,
    row_count: int,
    support_count: int,
    support_rate: float,
    author_count: int,
) -> str:
    if author_count >= 3 and row_count >= 16 and support_count >= 12 and support_rate >= 0.75:
        return "E4"
    if (
        author_count >= CROSS_AUTHOR_TRANSFER_MIN_AUTHORS
        and row_count >= CROSS_AUTHOR_TRANSFER_MIN_ROWS
        and support_count >= CROSS_AUTHOR_TRANSFER_MIN_SUPPORT
        and support_rate >= CROSS_AUTHOR_TRANSFER_MIN_RATE
    ):
        return "E3"
    return "E1"


def _support_rows_for_pattern(
    rows: list[dict[str, str]],
    *,
    route_scope: tuple[str, str, str],
    feature_name: str,
    feature_value: str,
) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if _route_scope(row) == route_scope and (row.get(feature_name, "") or "").strip() == feature_value
    ]


def _author_support_stats(
    rows: list[dict[str, str]],
    *,
    feature_name: str,
    feature_value: str,
) -> dict[str, dict[str, float]]:
    rows_by_author: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        author = (row.get("author", "") or "").strip()
        if not author:
            continue
        rows_by_author.setdefault(author, []).append(row)

    stats: dict[str, dict[str, float]] = {}
    for author, author_rows in rows_by_author.items():
        support_count = sum(
            1 for row in author_rows if (row.get(feature_name, "") or "").strip() == feature_value
        )
        row_count = len(author_rows)
        stats[author] = {
            "row_count": float(row_count),
            "support_count": float(support_count),
            "support_rate": support_count / row_count if row_count else 0.0,
        }
    return stats


def _opening_excerpt(text: str) -> str:
    normalized = (text or "").strip().replace("\r", "\n")
    if not normalized:
        return ""
    first_line = normalized.split("\n", 1)[0].strip()
    for splitter in ("。", "？", "?", "！", "!"):
        if splitter in first_line:
            return first_line.split(splitter, 1)[0].strip() + splitter
    return first_line[:80]


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _count_markers(text: str, markers: tuple[str, ...]) -> int:
    return sum(1 for marker in markers if marker in text)


def _to_float(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _to_int(value: object) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _fmt_float(value: float) -> str:
    return f"{value:.4f}"


def _hashed_id(prefix: str, *parts: str) -> str:
    joined = "|".join(part.strip() for part in parts if part is not None)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
