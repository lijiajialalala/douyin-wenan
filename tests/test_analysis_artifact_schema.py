from __future__ import annotations

import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.analysis.artifact_schema import load_artifact_schema, load_yaml_document


class ArtifactSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_evidence_record_schema_accepts_example(self) -> None:
        schema = load_artifact_schema(self.repo_root / "schemas" / "evidence_record_schema.yaml")
        document = load_yaml_document(self.repo_root / "examples" / "evidence_record.example.yaml")
        issues = schema.validate_document(document)
        self.assertFalse([issue for issue in issues if issue.level == "error"])

    def test_skill_card_schema_accepts_example(self) -> None:
        schema = load_artifact_schema(self.repo_root / "schemas" / "skill_card_schema.yaml")
        document = load_yaml_document(self.repo_root / "examples" / "skill_card.example.yaml")
        issues = schema.validate_document(document)
        self.assertFalse([issue for issue in issues if issue.level == "error"])

    def test_anti_skill_card_schema_accepts_example(self) -> None:
        schema = load_artifact_schema(self.repo_root / "schemas" / "anti_skill_card_schema.yaml")
        document = load_yaml_document(self.repo_root / "examples" / "anti_skill_card.example.yaml")
        issues = schema.validate_document(document)
        self.assertFalse([issue for issue in issues if issue.level == "error"])

    def test_composition_plan_schema_accepts_example(self) -> None:
        schema = load_artifact_schema(self.repo_root / "schemas" / "composition_plan_schema.yaml")
        document = load_yaml_document(self.repo_root / "examples" / "composition_plan.example.yaml")
        issues = schema.validate_document(document)
        self.assertFalse([issue for issue in issues if issue.level == "error"])

    def test_schema_rejects_wrong_list_field_type(self) -> None:
        schema = load_artifact_schema(self.repo_root / "schemas" / "skill_card_schema.yaml")
        document = load_yaml_document(self.repo_root / "examples" / "skill_card.example.yaml")
        document["formats"] = "debate_showdown"
        issues = schema.validate_document(document)
        self.assertTrue(any(issue.field == "formats" for issue in issues))


if __name__ == "__main__":
    unittest.main()
