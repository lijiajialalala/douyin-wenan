from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.analysis.artifact_schema import load_artifact_schema, load_yaml_document
from douyin_wenan.analysis.phase3 import distill_phase3_cards, write_phase3_exports
from douyin_wenan.common.csv_io import read_csv_rows


class Phase3DistillationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_distill_phase3_cards_builds_candidate_skill_and_anti_skill(self) -> None:
        evidence_records = [
            {
                "evidence_id": "ev_pos_001",
                "evidence_kind": "author_foundation_pattern",
                "evidence_origin": "foundation",
                "evidence_polarity": "positive",
                "transfer_scope": "author_local",
                "author": "柏拉图的石头",
                "scope": "same_author",
                "layer": "style_family",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "history",
                "primary_goal": "save",
                "style_family": "question_hook",
                "author_signature": "",
                "feature_name": "style_family",
                "feature_value": "question_hook",
                "metric_name": "high_low_rate_gap",
                "metric_value": "0.2083",
                "support_count": "13",
                "contradiction_count": "8",
                "support_prevalence": "0.72",
                "baseline_prevalence": "0.46",
                "support_sample_size": "18",
                "baseline_sample_size": "40",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "save",
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "为什么同样是太监干政，唐朝太监却能废立天子？",
                "evidence_refs": "2001|2002|2003",
                "notes": "same-author support",
            },
            {
                "evidence_id": "ev_neg_001",
                "evidence_kind": "negative_pattern",
                "evidence_origin": "differential",
                "evidence_polarity": "negative",
                "transfer_scope": "author_local",
                "author": "柏拉图的石头",
                "scope": "same_author",
                "layer": "general",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "history",
                "primary_goal": "completion",
                "style_family": "cold_explainer",
                "author_signature": "",
                "feature_name": "hook_type",
                "feature_value": "statement",
                "metric_name": "high_low_rate_gap",
                "metric_value": "-0.2500",
                "support_count": "15",
                "contradiction_count": "9",
                "support_prevalence": "0.58",
                "contrast_prevalence": "0.33",
                "support_sample_size": "24",
                "contrast_sample_size": "24",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "completion",
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "想必很多人都知道初中数学中的勾股定理。",
                "evidence_refs": "3001|3002|3003",
                "notes": "low-performer tendency",
            },
            {
                "evidence_id": "ev_weak_001",
                "evidence_kind": "contrast_finding",
                "evidence_origin": "differential",
                "evidence_polarity": "mixed",
                "transfer_scope": "author_local",
                "author": "柏拉图的石头",
                "scope": "same_author",
                "layer": "general",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "history",
                "primary_goal": "completion",
                "style_family": "question_hook",
                "author_signature": "",
                "feature_name": "cta_type",
                "feature_value": "interaction",
                "metric_name": "high_low_rate_gap",
                "metric_value": "0.1667",
                "support_count": "4",
                "contradiction_count": "0",
                "support_prevalence": "0.40",
                "contrast_prevalence": "0.23",
                "support_sample_size": "10",
                "contrast_sample_size": "10",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "completion",
                "confidence_grade": "E1",
                "ready_for_distillation": "no",
                "source_excerpt": "评论区告诉我你怎么看。",
                "evidence_refs": "4001|4002",
                "notes": "weak evidence only",
            },
        ]

        result = distill_phase3_cards(evidence_records)

        self.assertEqual(len(result.skill_cards), 1)
        self.assertEqual(len(result.anti_skill_cards), 1)
        self.assertEqual(len(result.skipped_records), 1)

        skill_card = result.skill_cards[0]
        self.assertEqual(skill_card["status"], "candidate")
        self.assertEqual(skill_card["card_type"], "skill")
        self.assertEqual(skill_card["skill_subtype"], "foundational_skill")
        self.assertEqual(skill_card["layer"], "style_family")
        self.assertIn("hook", skill_card["slots"])
        self.assertIn("question_hook", skill_card["style_families"])
        self.assertEqual(skill_card["production_actionability"], "direct")
        self.assertEqual(skill_card["transferability_level"], "content_type_specific")
        self.assertEqual(skill_card["promotion_status"], "author_local")
        self.assertEqual(skill_card["author_scope"], "柏拉图的石头")
        self.assertTrue(skill_card["misuse_risks"])
        self.assertEqual(skill_card["evidence_refs"], ["ev_pos_001"])

        anti_card = result.anti_skill_cards[0]
        self.assertEqual(anti_card["status"], "candidate")
        self.assertEqual(anti_card["skill_subtype"], "negative_pattern")
        self.assertEqual(anti_card["layer"], "general")
        self.assertIn("long_explainer", anti_card["formats"])
        self.assertEqual(anti_card["transferability_level"], "content_type_specific")
        self.assertEqual(anti_card["promotion_status"], "author_local")
        self.assertEqual(anti_card["author_scope"], "柏拉图的石头")
        self.assertTrue(anti_card["misuse_risks"])
        self.assertEqual(anti_card["evidence_refs"], ["ev_neg_001"])

    def test_write_phase3_exports_writes_schema_valid_yaml_cards(self) -> None:
        evidence_records = [
            {
                "evidence_id": "ev_pos_001",
                "evidence_kind": "author_foundation_pattern",
                "evidence_origin": "foundation",
                "evidence_polarity": "positive",
                "transfer_scope": "author_local",
                "author": "柏拉图的石头",
                "scope": "same_author",
                "layer": "style_family",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "history",
                "primary_goal": "save",
                "style_family": "question_hook",
                "author_signature": "",
                "feature_name": "style_family",
                "feature_value": "question_hook",
                "metric_name": "high_low_rate_gap",
                "metric_value": "0.2083",
                "support_count": "13",
                "contradiction_count": "8",
                "support_prevalence": "0.72",
                "baseline_prevalence": "0.46",
                "support_sample_size": "18",
                "baseline_sample_size": "40",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "save",
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "为什么同样是太监干政，唐朝太监却能废立天子？",
                "evidence_refs": "2001|2002|2003",
                "notes": "same-author support",
            },
            {
                "evidence_id": "ev_neg_001",
                "evidence_kind": "negative_pattern",
                "evidence_origin": "differential",
                "evidence_polarity": "negative",
                "transfer_scope": "author_local",
                "author": "柏拉图的石头",
                "scope": "same_author",
                "layer": "general",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "history",
                "primary_goal": "completion",
                "style_family": "cold_explainer",
                "author_signature": "",
                "feature_name": "hook_type",
                "feature_value": "statement",
                "metric_name": "high_low_rate_gap",
                "metric_value": "-0.2500",
                "support_count": "15",
                "contradiction_count": "9",
                "support_prevalence": "0.58",
                "contrast_prevalence": "0.33",
                "support_sample_size": "24",
                "contrast_sample_size": "24",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "completion",
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "想必很多人都知道初中数学中的勾股定理。",
                "evidence_refs": "3001|3002|3003",
                "notes": "low-performer tendency",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            result = distill_phase3_cards(evidence_records)
            paths = write_phase3_exports(result, tmp)

            skill_schema = load_artifact_schema(self.repo_root / "schemas" / "skill_card_schema.yaml")
            anti_schema = load_artifact_schema(self.repo_root / "schemas" / "anti_skill_card_schema.yaml")

            skill_card = load_yaml_document(paths["skills"][0])
            anti_card = load_yaml_document(paths["anti_skills"][0])
            self.assertFalse([issue for issue in skill_schema.validate_document(skill_card) if issue.level == "error"])
            self.assertFalse([issue for issue in anti_schema.validate_document(anti_card) if issue.level == "error"])
            self.assertTrue(paths["summary"].exists())
            self.assertTrue(paths["readable_zh"]["skills_csv"].exists())
            self.assertTrue(paths["readable_zh"]["anti_skills_md"].exists())
            self.assertNotIn("_source_author", skill_card)
            self.assertNotIn("_source_author", anti_card)
            self.assertEqual(skill_card["author_scope"], "柏拉图的石头")
            self.assertEqual(anti_card["author_scope"], "柏拉图的石头")

    def test_cross_author_transfer_records_become_cross_route_cards(self) -> None:
        evidence_records = [
            {
                "evidence_id": "ev_cross_001",
                "evidence_kind": "cross_author_transfer_pattern",
                "evidence_origin": "foundation",
                "evidence_polarity": "positive",
                "transfer_scope": "cross_author",
                "author": "多作者",
                "scope": "cross_author",
                "layer": "content_type",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "cognition",
                "primary_goal": "save",
                "style_family": "cold_explainer",
                "author_signature": "",
                "feature_name": "argument_shape",
                "feature_value": "stepwise_explainer",
                "metric_name": "cross_author_support",
                "metric_value": "0.42",
                "support_count": "28",
                "contradiction_count": "4",
                "support_prevalence": "0.70",
                "baseline_prevalence": "0.28",
                "support_sample_size": "40",
                "baseline_sample_size": "80",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "save",
                "confidence_grade": "E4",
                "ready_for_distillation": "yes",
                "source_excerpt": "先说第一个机制，再说第二个机制，最后回到结论。",
                "evidence_refs": "x1|x2|x3",
                "notes": "cross author transfer",
            }
        ]

        result = distill_phase3_cards(evidence_records)

        self.assertEqual(len(result.skill_cards), 1)
        card = result.skill_cards[0]
        self.assertEqual(card["skill_subtype"], "transferable_skill")
        self.assertEqual(card["status"], "active")
        self.assertEqual(card["transferability_level"], "cross_domain_rhetorical")
        self.assertEqual(card["promotion_status"], "cross_route_validated")
        self.assertNotIn("author_scope", card)
        self.assertIn("Do not apply outside the listed routing scope without fresh evidence.", card["misuse_risks"])

    def test_route_foundation_records_become_route_validated_cards(self) -> None:
        evidence_records = [
            {
                "evidence_id": "ev_route_001",
                "evidence_kind": "route_foundation_pattern",
                "evidence_origin": "route",
                "evidence_polarity": "positive",
                "transfer_scope": "route_local",
                "author": "多作者",
                "scope": "same_content_type",
                "layer": "general",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "cognition",
                "primary_goal": "follow",
                "style_family": "question_hook",
                "author_signature": "",
                "feature_name": "argument_shape",
                "feature_value": "stepwise_explainer",
                "metric_name": "route_prevalence",
                "metric_value": "0.75",
                "support_count": "12",
                "contradiction_count": "4",
                "support_prevalence": "0.75",
                "contrast_prevalence": "0.25",
                "baseline_prevalence": "",
                "support_sample_size": "16",
                "contrast_sample_size": "",
                "baseline_sample_size": "",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "follow",
                "confidence_grade": "E3",
                "ready_for_distillation": "yes",
                "source_excerpt": "先看第一层，再看第二层，最后回到结论。",
                "evidence_refs": "r1|r2|r3",
                "notes": "route foundation",
            }
        ]

        result = distill_phase3_cards(evidence_records)

        self.assertEqual(len(result.skill_cards), 1)
        card = result.skill_cards[0]
        self.assertEqual(card["skill_subtype"], "foundational_skill")
        self.assertEqual(card["promotion_status"], "route_validated")
        self.assertNotIn("author_scope", card)

    def test_write_phase3_exports_merges_author_scoped_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            author_a = distill_phase3_cards(
                [
                    {
                        "evidence_id": "ev_pos_a",
                        "evidence_kind": "author_foundation_pattern",
                        "evidence_origin": "foundation",
                        "evidence_polarity": "positive",
                        "transfer_scope": "author_local",
                        "author": "作者A",
                        "scope": "same_author",
                        "layer": "style_family",
                        "content_type": "concept_explainer",
                        "format": "long_explainer",
                        "domain": "history",
                        "primary_goal": "save",
                        "style_family": "question_hook",
                        "author_signature": "",
                        "feature_name": "style_family",
                        "feature_value": "question_hook",
                        "metric_name": "high_low_rate_gap",
                        "metric_value": "0.25",
                        "support_count": "6",
                        "contradiction_count": "2",
                        "support_prevalence": "0.70",
                        "baseline_prevalence": "0.45",
                        "support_sample_size": "10",
                        "baseline_sample_size": "20",
                        "route_content_type": "concept_explainer",
                        "route_format": "long_explainer",
                        "route_goal": "save",
                        "confidence_grade": "E2",
                        "ready_for_distillation": "yes",
                        "source_excerpt": "为什么会这样？",
                        "evidence_refs": "a1|a2",
                        "notes": "author a",
                    }
                ]
            )
            author_b = distill_phase3_cards(
                [
                    {
                        "evidence_id": "ev_neg_b",
                        "evidence_kind": "negative_pattern",
                        "evidence_origin": "differential",
                        "evidence_polarity": "negative",
                        "transfer_scope": "author_local",
                        "author": "作者B",
                        "scope": "same_author",
                        "layer": "general",
                        "content_type": "concept_explainer",
                        "format": "long_explainer",
                        "domain": "ai",
                        "primary_goal": "completion",
                        "style_family": "cold_explainer",
                        "author_signature": "",
                        "feature_name": "hook_type",
                        "feature_value": "statement",
                        "metric_name": "high_low_rate_gap",
                        "metric_value": "-0.25",
                        "support_count": "7",
                        "contradiction_count": "1",
                        "support_prevalence": "0.65",
                        "contrast_prevalence": "0.32",
                        "support_sample_size": "11",
                        "contrast_sample_size": "11",
                        "route_content_type": "concept_explainer",
                        "route_format": "long_explainer",
                        "route_goal": "completion",
                        "confidence_grade": "E2",
                        "ready_for_distillation": "yes",
                        "source_excerpt": "今天聊聊一个背景。",
                        "evidence_refs": "b1|b2",
                        "notes": "author b",
                    }
                ]
            )

            write_phase3_exports(author_a, tmp)
            write_phase3_exports(author_b, tmp)
            write_phase3_exports(author_a, tmp, target_authors=("作者A",))

            summary_rows = read_csv_rows(tmp / "exports" / "phase3_candidates.csv")
            skill_rows = read_csv_rows(tmp / "readable_zh" / "skills_zh.csv")
            anti_rows = read_csv_rows(tmp / "readable_zh" / "anti_skills_zh.csv")
            self.assertEqual({row["source_author"] for row in summary_rows}, {"作者A", "作者B"})
            self.assertEqual(len(summary_rows), 2)
            self.assertEqual({row["作者来源"] for row in skill_rows}, {"作者A"})
            self.assertEqual({row["作者来源"] for row in anti_rows}, {"作者B"})
            self.assertEqual({row["迁移层级"] for row in skill_rows}, {"内容类型专属"})
            self.assertEqual({row["验证范围"] for row in skill_rows}, {"作者局部"})
            self.assertTrue(all(row["误用风险"] for row in skill_rows + anti_rows))
            self.assertIn("基础能力：先提问题，再亮观点", (tmp / "readable_zh" / "skills_zh.md").read_text(encoding="utf-8"))
            self.assertIn("不要用平铺直叙的弱开头", (tmp / "readable_zh" / "anti_skills_zh.md").read_text(encoding="utf-8"))
            self.assertTrue((tmp / "assets" / "skills").exists())
            self.assertTrue((tmp / "assets" / "anti_skills").exists())

    def test_write_phase3_exports_accepts_legacy_summary_without_source_author(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            exports_dir = tmp / "exports"
            exports_dir.mkdir(parents=True, exist_ok=True)
            result = distill_phase3_cards(
                [
                    {
                        "evidence_id": "ev_pos_new",
                        "evidence_kind": "author_foundation_pattern",
                        "evidence_origin": "foundation",
                        "evidence_polarity": "positive",
                        "transfer_scope": "author_local",
                        "author": "作者C",
                        "scope": "same_author",
                        "layer": "style_family",
                        "content_type": "concept_explainer",
                        "format": "long_explainer",
                        "domain": "history",
                        "primary_goal": "save",
                        "style_family": "question_hook",
                        "author_signature": "",
                        "feature_name": "style_family",
                        "feature_value": "question_hook",
                        "metric_name": "high_low_rate_gap",
                        "metric_value": "0.25",
                        "support_count": "6",
                        "contradiction_count": "2",
                        "support_prevalence": "0.70",
                        "baseline_prevalence": "0.45",
                        "support_sample_size": "10",
                        "baseline_sample_size": "20",
                        "route_content_type": "concept_explainer",
                        "route_format": "long_explainer",
                        "route_goal": "save",
                        "confidence_grade": "E2",
                        "ready_for_distillation": "yes",
                        "source_excerpt": "为什么会这样？",
                        "evidence_refs": "c1|c2",
                        "notes": "author c",
                    }
                ]
            )
            legacy_card_id = result.skill_cards[0]["card_id"]
            (exports_dir / "phase3_candidates.csv").write_text(
                "card_id,card_kind,title,status,layer,evidence_refs\n"
                f"{legacy_card_id},skill,Legacy Card,candidate,general,ev_legacy\n",
                encoding="utf-8-sig",
            )

            write_phase3_exports(result, tmp)

            summary_rows = read_csv_rows(tmp / "exports" / "phase3_candidates.csv")
            self.assertEqual(len(summary_rows), 1)
            self.assertTrue(any(row["source_author"] == "作者C" for row in summary_rows))

    def test_write_phase3_exports_clears_author_scoped_outputs_when_author_now_has_zero_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            author_a = distill_phase3_cards(
                [
                    {
                        "evidence_id": "ev_pos_a",
                        "evidence_kind": "author_foundation_pattern",
                        "evidence_origin": "foundation",
                        "evidence_polarity": "positive",
                        "transfer_scope": "author_local",
                        "author": "作者A",
                        "scope": "same_author",
                        "layer": "style_family",
                        "content_type": "concept_explainer",
                        "format": "long_explainer",
                        "domain": "history",
                        "primary_goal": "save",
                        "style_family": "question_hook",
                        "author_signature": "",
                        "feature_name": "style_family",
                        "feature_value": "question_hook",
                        "metric_name": "high_low_rate_gap",
                        "metric_value": "0.25",
                        "support_count": "6",
                        "contradiction_count": "2",
                        "support_prevalence": "0.70",
                        "baseline_prevalence": "0.45",
                        "support_sample_size": "10",
                        "baseline_sample_size": "20",
                        "route_content_type": "concept_explainer",
                        "route_format": "long_explainer",
                        "route_goal": "save",
                        "confidence_grade": "E2",
                        "ready_for_distillation": "yes",
                        "source_excerpt": "为什么会这样？",
                        "evidence_refs": "a1|a2",
                        "notes": "author a",
                    }
                ]
            )
            author_b = distill_phase3_cards(
                [
                    {
                        "evidence_id": "ev_neg_b",
                        "evidence_kind": "negative_pattern",
                        "evidence_origin": "differential",
                        "evidence_polarity": "negative",
                        "transfer_scope": "author_local",
                        "author": "作者B",
                        "scope": "same_author",
                        "layer": "general",
                        "content_type": "concept_explainer",
                        "format": "long_explainer",
                        "domain": "ai",
                        "primary_goal": "completion",
                        "style_family": "cold_explainer",
                        "author_signature": "",
                        "feature_name": "hook_type",
                        "feature_value": "statement",
                        "metric_name": "high_low_rate_gap",
                        "metric_value": "-0.25",
                        "support_count": "7",
                        "contradiction_count": "1",
                        "support_prevalence": "0.65",
                        "contrast_prevalence": "0.32",
                        "support_sample_size": "11",
                        "contrast_sample_size": "11",
                        "route_content_type": "concept_explainer",
                        "route_format": "long_explainer",
                        "route_goal": "completion",
                        "confidence_grade": "E2",
                        "ready_for_distillation": "yes",
                        "source_excerpt": "今天聊聊一个背景。",
                        "evidence_refs": "b1|b2",
                        "notes": "author b",
                    }
                ]
            )

            write_phase3_exports(author_a, tmp)
            write_phase3_exports(author_b, tmp)
            author_a_card_ids = {card["card_id"] for card in author_a.skill_cards + author_a.anti_skill_cards}
            author_b_card_ids = {card["card_id"] for card in author_b.skill_cards + author_b.anti_skill_cards}
            write_phase3_exports(
                distill_phase3_cards([]),
                tmp,
                target_authors=("作者A",),
            )

            summary_rows = read_csv_rows(tmp / "exports" / "phase3_candidates.csv")
            skill_rows = read_csv_rows(tmp / "readable_zh" / "skills_zh.csv")
            anti_rows = read_csv_rows(tmp / "readable_zh" / "anti_skills_zh.csv")
            self.assertEqual({row["source_author"] for row in summary_rows}, {"作者B"})
            self.assertFalse(any("作者A" == row["source_author"] for row in summary_rows))
            self.assertEqual(skill_rows, [])
            self.assertEqual({row["作者来源"] for row in anti_rows}, {"作者B"})
            self.assertIn("暂无导出结果。", (tmp / "readable_zh" / "skills_zh.md").read_text(encoding="utf-8"))
            self.assertIn("不要用平铺直叙的弱开头", (tmp / "readable_zh" / "anti_skills_zh.md").read_text(encoding="utf-8"))
            for card_id in author_a_card_ids:
                self.assertFalse((tmp / "assets" / "skills" / f"{card_id}.yaml").exists())
                self.assertFalse((tmp / "assets" / "anti_skills" / f"{card_id}.yaml").exists())
            self.assertTrue(
                any(
                    (tmp / "assets" / "skills" / f"{card_id}.yaml").exists()
                    or (tmp / "assets" / "anti_skills" / f"{card_id}.yaml").exists()
                    for card_id in author_b_card_ids
                )
            )

    def test_distill_phase3_skips_low_value_positive_descriptor_patterns(self) -> None:
        evidence_records = [
            {
                "evidence_id": "ev_pos_skip_001",
                "evidence_kind": "differential_gain_pattern",
                "evidence_origin": "differential",
                "evidence_polarity": "positive",
                "transfer_scope": "author_local",
                "author": "作者A",
                "scope": "same_author",
                "layer": "general",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "history",
                "primary_goal": "completion",
                "style_family": "cold_explainer",
                "author_signature": "",
                "feature_name": "hook_type",
                "feature_value": "statement",
                "metric_name": "high_low_rate_gap",
                "metric_value": "0.23",
                "support_count": "9",
                "contradiction_count": "3",
                "support_prevalence": "0.63",
                "contrast_prevalence": "0.40",
                "support_sample_size": "14",
                "contrast_sample_size": "14",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "completion",
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "今天聊聊一个背景。",
                "evidence_refs": "a1|a2",
                "notes": "descriptive but not reusable enough",
            }
        ]

        result = distill_phase3_cards(evidence_records)
        self.assertEqual(result.skill_cards, [])
        self.assertEqual(result.anti_skill_cards, [])
        self.assertEqual(len(result.skipped_records), 1)

    def test_distill_phase3_skips_low_value_negative_descriptor_patterns(self) -> None:
        evidence_records = [
            {
                "evidence_id": "ev_neg_skip_001",
                "evidence_kind": "negative_pattern",
                "evidence_origin": "differential",
                "evidence_polarity": "negative",
                "transfer_scope": "author_local",
                "author": "作者A",
                "scope": "same_author",
                "layer": "general",
                "content_type": "concept_explainer",
                "format": "long_explainer",
                "domain": "history",
                "primary_goal": "save",
                "style_family": "question_hook",
                "author_signature": "",
                "feature_name": "opening_problem_presence",
                "feature_value": "yes",
                "metric_name": "high_low_rate_gap",
                "metric_value": "-0.23",
                "support_count": "9",
                "contradiction_count": "3",
                "support_prevalence": "0.41",
                "contrast_prevalence": "0.64",
                "support_sample_size": "14",
                "contrast_sample_size": "14",
                "route_content_type": "concept_explainer",
                "route_format": "long_explainer",
                "route_goal": "save",
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "为什么会这样？",
                "evidence_refs": "n1|n2",
                "notes": "negative but not structurally reusable",
            }
        ]

        result = distill_phase3_cards(evidence_records)
        self.assertEqual(result.skill_cards, [])
        self.assertEqual(result.anti_skill_cards, [])
        self.assertEqual(len(result.skipped_records), 1)


if __name__ == "__main__":
    unittest.main()
