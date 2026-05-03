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
                "evidence_kind": "corroborated_pattern",
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
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "为什么同样是太监干政，唐朝太监却能废立天子？",
                "evidence_refs": "2001|2002|2003",
                "notes": "same-author support",
            },
            {
                "evidence_id": "ev_neg_001",
                "evidence_kind": "rejected_pattern",
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
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "想必很多人都知道初中数学中的勾股定理。",
                "evidence_refs": "3001|3002|3003",
                "notes": "low-performer tendency",
            },
            {
                "evidence_id": "ev_weak_001",
                "evidence_kind": "contrast_finding",
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
        self.assertEqual(skill_card["layer"], "style_family")
        self.assertIn("hook", skill_card["slots"])
        self.assertIn("question_hook", skill_card["style_families"])
        self.assertEqual(skill_card["evidence_refs"], ["ev_pos_001"])

        anti_card = result.anti_skill_cards[0]
        self.assertEqual(anti_card["status"], "candidate")
        self.assertEqual(anti_card["layer"], "general")
        self.assertIn("long_explainer", anti_card["formats"])
        self.assertEqual(anti_card["evidence_refs"], ["ev_neg_001"])

    def test_write_phase3_exports_writes_schema_valid_yaml_cards(self) -> None:
        evidence_records = [
            {
                "evidence_id": "ev_pos_001",
                "evidence_kind": "corroborated_pattern",
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
                "confidence_grade": "E2",
                "ready_for_distillation": "yes",
                "source_excerpt": "为什么同样是太监干政，唐朝太监却能废立天子？",
                "evidence_refs": "2001|2002|2003",
                "notes": "same-author support",
            },
            {
                "evidence_id": "ev_neg_001",
                "evidence_kind": "rejected_pattern",
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
            self.assertNotIn("_source_author", skill_card)
            self.assertNotIn("_source_author", anti_card)

    def test_write_phase3_exports_merges_author_scoped_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            author_a = distill_phase3_cards(
                [
                    {
                        "evidence_id": "ev_pos_a",
                        "evidence_kind": "corroborated_pattern",
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
                        "evidence_kind": "rejected_pattern",
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

            summary_rows = read_csv_rows(tmp / "exports" / "phase3_candidates.csv")
            self.assertEqual({row["source_author"] for row in summary_rows}, {"作者A", "作者B"})
            self.assertEqual(len(summary_rows), 2)
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
                        "evidence_kind": "corroborated_pattern",
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


if __name__ == "__main__":
    unittest.main()
