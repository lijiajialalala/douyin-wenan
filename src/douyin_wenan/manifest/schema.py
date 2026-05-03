from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    required: bool
    type_name: str
    allowed: tuple[str, ...] = ()
    default: str = ""
    description: str = ""


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    field: str
    message: str


@dataclass(frozen=True)
class ManifestSchema:
    version: str
    description: str
    columns: tuple[ColumnSpec, ...]
    row_invariants: tuple[str, ...]
    creation_defaults: dict[str, str]

    @property
    def fieldnames(self) -> list[str]:
        return [column.name for column in self.columns]

    @property
    def column_map(self) -> dict[str, ColumnSpec]:
        return {column.name: column for column in self.columns}

    def make_default_row(self) -> dict[str, str]:
        row = {name: "" for name in self.fieldnames}
        for name, value in self.creation_defaults.items():
            if name in row:
                row[name] = value
        return row

    def validate_header(self, fieldnames: list[str]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        expected = self.fieldnames
        if fieldnames != expected:
            issues.append(
                ValidationIssue(
                    level="error",
                    field="__header__",
                    message=f"Header mismatch. expected={expected} actual={fieldnames}",
                )
            )
        return issues

    def validate_row(self, row: dict[str, str], *, strict: bool = False) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for column in self.columns:
            value = (row.get(column.name, "") or "").strip()
            if column.required and value == "":
                issues.append(ValidationIssue("error", column.name, "required field is empty"))
                continue
            if value == "":
                continue

            if column.allowed and value not in column.allowed:
                issues.append(
                    ValidationIssue(
                        "error",
                        column.name,
                        f"invalid value '{value}', allowed={list(column.allowed)}",
                    )
                )

            if column.type_name == "integer":
                try:
                    int(value)
                except ValueError:
                    issues.append(ValidationIssue("error", column.name, f"invalid integer '{value}'"))
            elif column.type_name == "number":
                try:
                    float(value)
                except ValueError:
                    issues.append(ValidationIssue("error", column.name, f"invalid number '{value}'"))

        # Soft invariants by default. Promote to errors only when strict=True.
        issues.extend(self._validate_soft_invariants(row, strict=strict))
        return issues

    def _validate_soft_invariants(self, row: dict[str, str], *, strict: bool) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        level = "error" if strict else "warning"

        if row.get("asr_status") == "ok" and row.get("download_status") != "ok":
            issues.append(ValidationIssue(level, "asr_status", "asr ok requires download ok"))
        if row.get("download_status") == "ok" and not (row.get("raw_video_path") or "").strip():
            issues.append(ValidationIssue(level, "raw_video_path", "download ok should set raw_video_path"))
        if row.get("txt_sync_status") == "ok" and row.get("asr_status") != "ok":
            issues.append(ValidationIssue(level, "txt_sync_status", "txt sync ok requires asr ok"))
        if row.get("dedup_status") not in {"", "unknown"} and row.get("txt_sync_status") != "ok":
            issues.append(ValidationIssue(level, "dedup_status", "dedup classification requires txt sync ok"))
        if row.get("asr_quality_grade") and row.get("asr_status") != "ok":
            issues.append(ValidationIssue(level, "asr_quality_grade", "quality grade should be set only after asr ok"))
        if row.get("asr_status") == "ok" and not (row.get("asr_text_path") or "").strip():
            issues.append(ValidationIssue(level, "asr_text_path", "asr ok should set asr_text_path"))
        if row.get("txt_sync_status") == "ok" and not (row.get("txt_path") or "").strip():
            issues.append(ValidationIssue(level, "txt_path", "txt path should be set when txt sync is ok"))
        for field in [
            "raw_video_path",
            "raw_audio_path",
            "asr_raw_text_path",
            "asr_text_path",
            "asr_correction_json_path",
            "legacy_txt_path",
            "txt_path",
        ]:
            value = (row.get(field, "") or "").strip()
            if value and not Path(value).is_absolute():
                issues.append(ValidationIssue(level, field, f"{field} should be absolute when set"))

        return issues


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_schema_path() -> Path:
    return _repo_root() / "schemas" / "manifest_columns.yaml"


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"Invalid bool value: {value}")


def _parse_inline_list(value: str) -> tuple[str, ...]:
    text = value.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return ()
    inner = text[1:-1].strip()
    if not inner:
        return ()
    return tuple(item.strip() for item in inner.split(","))


def load_manifest_schema(path: Path | None = None) -> ManifestSchema:
    schema_path = path or default_schema_path()
    version = ""
    description = ""
    columns: list[ColumnSpec] = []
    row_invariants: list[str] = []
    creation_defaults: dict[str, str] = {}

    section: str | None = None
    current_column: dict[str, object] | None = None

    for raw_line in schema_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            if current_column is not None:
                columns.append(_column_from_dict(current_column))
                current_column = None

            if stripped in {"columns:", "row_invariants:", "creation_defaults:"}:
                section = stripped[:-1]
                continue

            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = _strip_quotes(value.strip())
                if key == "version":
                    version = value
                elif key == "description":
                    description = value
            continue

        if section == "columns":
            if stripped.startswith("- name:"):
                if current_column is not None:
                    columns.append(_column_from_dict(current_column))
                name_value = stripped.split(":", 1)[1].strip()
                current_column = {"name": _strip_quotes(name_value)}
                continue

            if current_column is not None and ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "required":
                    current_column[key] = _parse_bool(value)
                elif key == "allowed":
                    current_column[key] = _parse_inline_list(value)
                else:
                    current_column[key] = _strip_quotes(value)
            continue

        if section == "row_invariants" and stripped.startswith("- rule:"):
            rule = stripped.split(":", 1)[1].strip()
            row_invariants.append(_strip_quotes(rule))
            continue

        if section == "creation_defaults" and ":" in stripped:
            key, value = stripped.split(":", 1)
            creation_defaults[key.strip()] = _strip_quotes(value.strip())

    if current_column is not None:
        columns.append(_column_from_dict(current_column))

    if not columns:
        raise ValueError(f"No columns parsed from schema file: {schema_path}")

    return ManifestSchema(
        version=version or "1",
        description=description,
        columns=tuple(columns),
        row_invariants=tuple(row_invariants),
        creation_defaults=creation_defaults,
    )


def _column_from_dict(raw: dict[str, object]) -> ColumnSpec:
    return ColumnSpec(
        name=str(raw["name"]),
        required=bool(raw.get("required", False)),
        type_name=str(raw.get("type", "string")),
        allowed=tuple(raw.get("allowed", ())),
        default=str(raw.get("default", "")),
        description=str(raw.get("description", "")),
    )
