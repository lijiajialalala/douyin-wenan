from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from douyin_wenan.common.csv_io import read_csv_rows, write_csv_rows
from douyin_wenan.paths import ensure_parent_dir

from .schema import ManifestSchema, ValidationIssue


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


class ManifestRepository:
    def __init__(self, path: Path, schema: ManifestSchema) -> None:
        self.path = path
        self.schema = schema

    def exists(self) -> bool:
        return self.path.exists()

    def init_empty(self, *, overwrite: bool = False) -> None:
        if self.path.exists() and not overwrite:
            return
        ensure_parent_dir(self.path)
        write_csv_rows(self.path, self.schema.fieldnames, [])

    def migrate_to_schema(self) -> None:
        if not self.path.exists():
            self.init_empty()
            return

        rows = read_csv_rows(self.path)
        normalized = [self._normalize_row_shape(row) for row in rows]
        errors: list[ValidationIssue] = []
        for row in normalized:
            for issue in self.schema.validate_row(row, strict=False):
                if issue.level == "error":
                    errors.append(issue)
        if errors:
            raise ValueError(self._format_errors(tuple(errors)))

        ensure_parent_dir(self.path)
        write_csv_rows(self.path, self.schema.fieldnames, normalized)

    def load_rows(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        rows = read_csv_rows(self.path)
        self._validate_rows(rows)
        return [self._normalize_row_shape(row) for row in rows]

    def save_rows(self, rows: list[dict[str, str]]) -> ValidationReport:
        normalized = [self._normalize_row_shape(row) for row in rows]
        report = self._validate_rows(normalized)
        if not report.ok:
            raise ValueError(self._format_errors(report.errors))
        ensure_parent_dir(self.path)
        write_csv_rows(self.path, self.schema.fieldnames, normalized)
        return report

    def upsert_row(self, row: dict[str, str], *, key_field: str = "work_id") -> ValidationReport:
        rows = self.load_rows()
        key = (row.get(key_field, "") or "").strip()
        if not key:
            raise ValueError(f"Cannot upsert row without {key_field}")

        replaced = False
        normalized_row = self._normalize_row_shape(row)
        for index, existing in enumerate(rows):
            if (existing.get(key_field, "") or "").strip() == key:
                rows[index] = normalized_row
                replaced = True
                break
        if not replaced:
            rows.append(normalized_row)
        return self.save_rows(rows)

    def index_by(self, field: str) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for row in self.load_rows():
            key = (row.get(field, "") or "").strip()
            if key:
                result[key] = row
        return result

    def _normalize_row_shape(self, row: dict[str, str]) -> dict[str, str]:
        normalized = self.schema.make_default_row()
        for field in self.schema.fieldnames:
            value = row.get(field, "")
            normalized[field] = "" if value is None else str(value)
        return normalized

    def _validate_rows(self, rows: list[dict[str, str]]) -> ValidationReport:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        if self.path.exists():
            with self.path.open("r", encoding="utf-8-sig", newline="") as fh:
                header = fh.readline().lstrip("\ufeff").strip()
            if header:
                actual = header.split(",")
                header_issues = self.schema.validate_header(actual)
                for issue in header_issues:
                    if issue.level == "error":
                        errors.append(issue)
                    else:
                        warnings.append(issue)

        seen_work_ids: set[str] = set()
        for row in rows:
            issues = self.schema.validate_row(row, strict=False)
            for issue in issues:
                if issue.level == "error":
                    errors.append(issue)
                else:
                    warnings.append(issue)

            work_id = (row.get("work_id", "") or "").strip()
            if work_id:
                if work_id in seen_work_ids:
                    errors.append(ValidationIssue("error", "work_id", f"duplicate work_id '{work_id}'"))
                seen_work_ids.add(work_id)

        return ValidationReport(errors=tuple(errors), warnings=tuple(warnings))

    @staticmethod
    def _format_errors(errors: tuple[ValidationIssue, ...]) -> str:
        return "; ".join(f"{issue.field}: {issue.message}" for issue in errors)
