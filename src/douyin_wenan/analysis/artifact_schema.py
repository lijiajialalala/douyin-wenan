from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from douyin_wenan.manifest.schema import ValidationIssue


@dataclass(frozen=True)
class ArtifactFieldSpec:
    name: str
    required: bool
    type_name: str
    allowed: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class ArtifactSchema:
    version: str
    description: str
    fields: tuple[ArtifactFieldSpec, ...]
    row_invariants: tuple[str, ...]

    @property
    def fieldnames(self) -> list[str]:
        return [field.name for field in self.fields]

    def validate_document(self, document: dict[str, object]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for field in self.fields:
            value = document.get(field.name)
            if field.required and _is_missing(value):
                issues.append(ValidationIssue("error", field.name, "required field is empty"))
                continue
            if value is None:
                continue
            issues.extend(_validate_field_value(field, value))
        return issues


def load_yaml_document(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML document object: {path}")
    return payload


def load_artifact_schema(path: Path) -> ArtifactSchema:
    payload = load_yaml_document(path)
    fields_raw = payload.get("fields", [])
    if not isinstance(fields_raw, list) or not fields_raw:
        raise ValueError(f"No fields parsed from schema file: {path}")

    fields: list[ArtifactFieldSpec] = []
    for field_raw in fields_raw:
        if not isinstance(field_raw, dict):
            continue
        allowed_raw = field_raw.get("allowed", [])
        allowed = tuple(str(item) for item in allowed_raw) if isinstance(allowed_raw, list) else ()
        fields.append(
            ArtifactFieldSpec(
                name=str(field_raw.get("name", "")).strip(),
                required=bool(field_raw.get("required", False)),
                type_name=str(field_raw.get("type", "string")).strip() or "string",
                allowed=allowed,
                description=str(field_raw.get("description", "")).strip(),
            )
        )

    row_invariants_raw = payload.get("row_invariants", [])
    row_invariants: list[str] = []
    if isinstance(row_invariants_raw, list):
        for invariant in row_invariants_raw:
            if isinstance(invariant, dict) and "rule" in invariant:
                row_invariants.append(str(invariant["rule"]).strip())

    return ArtifactSchema(
        version=str(payload.get("version", "1")).strip() or "1",
        description=str(payload.get("description", "")).strip(),
        fields=tuple(fields),
        row_invariants=tuple(row_invariants),
    )


def _validate_field_value(field: ArtifactFieldSpec, value: object) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if field.type_name == "string":
        if not isinstance(value, str):
            issues.append(ValidationIssue("error", field.name, f"expected string, got {type(value).__name__}"))
            return issues
        stripped = value.strip()
        if field.allowed and stripped not in field.allowed:
            issues.append(ValidationIssue("error", field.name, f"invalid value '{stripped}'"))
        return issues

    if field.type_name == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            issues.append(ValidationIssue("error", field.name, f"expected integer, got {type(value).__name__}"))
        return issues

    if field.type_name == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            issues.append(ValidationIssue("error", field.name, f"expected number, got {type(value).__name__}"))
        return issues

    if field.type_name == "string_list":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            issues.append(ValidationIssue("error", field.name, "expected list[str]"))
        return issues

    if field.type_name == "object":
        if not isinstance(value, dict):
            issues.append(ValidationIssue("error", field.name, f"expected object, got {type(value).__name__}"))
        return issues

    if field.type_name == "object_list":
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            issues.append(ValidationIssue("error", field.name, "expected list[object]"))
        return issues

    return issues


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    return False
