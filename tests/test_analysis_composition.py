from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.analysis.artifact_schema import load_artifact_schema, load_yaml_document
from douyin_wenan.analysis.composition import CompositionRequest, compose_plan, write_composition_plan


class CompositionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_compose_plan_resolves_structure_over_style_and_signature(self) -> None:
        skill_cards = [
            self._skill_card(
                card_id="debate_structure",
                title="Debate Structure",
                layer="content_type",
                priority=95,
                hardness="required",
                content_types=["comparison_review"],
                formats=["debate_showdown"],
                goals=["interaction"],
                slots=["hook", "comparison", "close"],
            ),
            self._skill_card(
                card_id="interaction_cta",
                title="Interaction CTA",
                layer="general",
                priority=80,
                hardness="required",
                goals=["interaction"],
                slots=["cta"],
            ),
            self._skill_card(
                card_id="strong_claim_hook",
                title="Strong Claim Hook",
                layer="style_family",
                priority=82,
                hardness="preferred",
                style_families=["strong_claim"],
                slots=["hook"],
            ),
            self._skill_card(
                card_id="slow_literary_setup",
                title="Slow Literary Setup",
                card_type="signature_pattern",
                layer="author_signature",
                priority=88,
                hardness="preferred",
                author_scope="柏拉图的石头",
                author_signatures=["slow_literary_setup"],
                slots=["hook"],
            ),
        ]
        anti_skill_cards = [
            self._anti_skill_card(
                card_id="avoid_slow_warmup",
                title="Avoid Slow Warmup",
                priority=90,
                hardness="required",
                formats=["debate_showdown"],
                goals=["interaction"],
            )
        ]

        plan = compose_plan(
            skill_cards,
            anti_skill_cards,
            CompositionRequest(
                domain="ai",
                format="debate_showdown",
                goal="interaction",
                content_type="comparison_review",
                style_family="strong_claim",
                author_signature="slow_literary_setup",
                author_scope="柏拉图的石头",
            ),
        )

        self.assertEqual(plan["status"], "resolved")
        self.assertEqual(plan["slot_ownership"]["hook"], "debate_structure")
        self.assertEqual(plan["slot_ownership"]["comparison"], "debate_structure")
        self.assertEqual(plan["slot_ownership"]["close"], "debate_structure")
        self.assertEqual(plan["slot_ownership"]["cta"], "interaction_cta")
        self.assertIn("avoid_slow_warmup", plan["selected_cards"])
        self.assertIn("strong_claim_hook", plan["dropped_cards"])
        self.assertIn("slow_literary_setup", plan["dropped_cards"])
        self.assertTrue(
            any(
                decision["slot"] == "hook"
                and decision["winner"] == "debate_structure"
                and decision["dropped"] == "slow_literary_setup"
                for decision in plan["override_decisions"]
            )
        )

    def test_compose_plan_requires_review_for_tied_required_same_slot(self) -> None:
        skill_cards = [
            self._skill_card(
                card_id="hook_a",
                title="Hook A",
                layer="general",
                priority=80,
                hardness="required",
                slots=["hook"],
            ),
            self._skill_card(
                card_id="hook_b",
                title="Hook B",
                layer="general",
                priority=80,
                hardness="required",
                slots=["hook"],
            ),
        ]

        plan = compose_plan(
            skill_cards,
            [],
            CompositionRequest(
                domain="history",
                format="long_explainer",
                goal="completion",
                content_type="concept_explainer",
            ),
        )

        self.assertEqual(plan["status"], "review_required")
        self.assertTrue(plan["unresolved_conflicts"])
        self.assertIn("hook_a", plan["dropped_cards"])
        self.assertIn("hook_b", plan["dropped_cards"])

    def test_compose_plan_rechecks_remaining_cards_after_explicit_override(self) -> None:
        skill_cards = [
            self._skill_card(
                card_id="hook_a",
                title="Hook A",
                layer="general",
                priority=100,
                hardness="required",
                slots=["hook"],
            ),
            self._skill_card(
                card_id="hook_b",
                title="Hook B",
                layer="general",
                priority=90,
                hardness="required",
                slots=["hook"],
            ),
            self._skill_card(
                card_id="hook_c",
                title="Hook C",
                layer="general",
                priority=10,
                hardness="required",
                slots=["hook"],
                overrides=["hook_a"],
            ),
        ]

        plan = compose_plan(
            skill_cards,
            [],
            CompositionRequest(
                domain="history",
                format="long_explainer",
                goal="completion",
                content_type="concept_explainer",
            ),
        )

        self.assertEqual(plan["status"], "resolved")
        self.assertEqual(plan["slot_ownership"]["hook"], "hook_b")
        self.assertEqual(plan["selected_cards"], ["hook_b"])
        self.assertIn("hook_a", plan["dropped_cards"])
        self.assertIn("hook_c", plan["dropped_cards"])
        self.assertTrue(
            any(
                decision["slot"] == "hook"
                and decision["winner"] == "hook_c"
                and decision["dropped"] == "hook_a"
                for decision in plan["override_decisions"]
            )
        )
        self.assertTrue(
            any(
                decision["slot"] == "hook"
                and decision["winner"] == "hook_b"
                and decision["dropped"] == "hook_c"
                for decision in plan["override_decisions"]
            )
        )

    def test_write_composition_plan_writes_schema_valid_yaml(self) -> None:
        skill_cards = [
            self._skill_card(
                card_id="long_explainer_claim",
                title="Long Explainer Claim",
                layer="content_type",
                priority=90,
                hardness="required",
                content_types=["historical_interpretation"],
                formats=["long_explainer"],
                slots=["hook", "claim", "close"],
            ),
        ]

        plan = compose_plan(
            skill_cards,
            [],
            CompositionRequest(
                domain="history",
                format="long_explainer",
                goal="completion",
                content_type="historical_interpretation",
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "composition.yaml"
            path = write_composition_plan(plan, output_path)
            schema = load_artifact_schema(self.repo_root / "schemas" / "composition_plan_schema.yaml")
            payload = load_yaml_document(path)
            self.assertFalse([issue for issue in schema.validate_document(payload) if issue.level == "error"])

    def _skill_card(
        self,
        *,
        card_id: str,
        title: str,
        layer: str,
        priority: int,
        hardness: str,
        slots: list[str],
        card_type: str = "skill",
        content_types: list[str] | None = None,
        formats: list[str] | None = None,
        domains: list[str] | None = None,
        goals: list[str] | None = None,
        style_families: list[str] | None = None,
        author_scope: str = "",
        author_signatures: list[str] | None = None,
        overrides: list[str] | None = None,
        status: str = "candidate",
    ) -> dict[str, object]:
        return {
            "card_id": card_id,
            "title": title,
            "card_type": card_type,
            "status": status,
            "layer": layer,
            "priority": priority,
            "hardness": hardness,
            "content_types": content_types or [],
            "formats": formats or [],
            "domains": domains or [],
            "goals": goals or [],
            "style_families": style_families or [],
            "author_scope": author_scope,
            "author_signatures": author_signatures or [],
            "trigger_conditions": ["Use when routing matches."],
            "avoid_conditions": [],
            "slots": slots,
            "depends_on": [],
            "overrides": overrides or [],
            "incompatible_with": [],
            "input_context": ["Context"],
            "execution_steps": ["Step"],
            "output_contract": ["Contract"],
            "evaluation_checks": ["Check"],
            "positive_examples": ["Positive"],
            "counter_examples": ["Negative"],
            "evidence_refs": ["ev_001"],
            "notes": "",
        }

    def _anti_skill_card(
        self,
        *,
        card_id: str,
        title: str,
        priority: int,
        hardness: str,
        formats: list[str] | None = None,
        goals: list[str] | None = None,
        status: str = "candidate",
    ) -> dict[str, object]:
        return {
            "card_id": card_id,
            "title": title,
            "status": status,
            "layer": "general",
            "priority": priority,
            "hardness": hardness,
            "content_types": [],
            "formats": formats or [],
            "domains": [],
            "goals": goals or [],
            "failure_pattern": "failure",
            "detection_signals": ["signal"],
            "likely_causes": ["cause"],
            "prevention_actions": ["prevent"],
            "bad_examples": ["bad"],
            "repair_examples": ["repair"],
            "evaluation_checks": ["check"],
            "evidence_refs": ["ev_anti_001"],
            "notes": "",
        }


if __name__ == "__main__":
    unittest.main()
