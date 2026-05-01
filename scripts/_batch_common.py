from __future__ import annotations

import argparse
from pathlib import Path

try:
    from _bootstrap import configure_stdio, ensure_src_path
except ModuleNotFoundError:
    from scripts._bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.config import load_runtime_config
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema


def build_batch_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", type=Path, default=None, help="Path to local config yaml")
    parser.add_argument("--manifest-path", type=Path, default=None, help="Override manifest file path")
    parser.add_argument("--author", type=str, default="", help="Only select one author")
    parser.add_argument("--limit", type=int, default=0, help="Only select the first N rows")
    return parser


def load_manifest_rows(config_path: Path | None, manifest_path_override: Path | None) -> tuple[Path, list[dict[str, str]]]:
    config = load_runtime_config(config_path)
    manifest_path = manifest_path_override or config.manifest_path
    schema = load_manifest_schema()
    repo = ManifestRepository(manifest_path, schema)
    repo.migrate_to_schema()
    return manifest_path, repo.load_rows()


def print_batch_preview(
    *,
    stage: str,
    manifest_path: Path,
    rows: list[dict[str, str]],
    reference_field: str,
) -> None:
    print(f"stage={stage}")
    print(f"manifest_path={manifest_path}")
    print(f"selected={len(rows)}")
    for row in rows:
        reference_value = (row.get(reference_field, "") or "").strip()
        title = (row.get("title", "") or "").strip()
        print(f"{row['work_id']}\t{row['author']}\t{title}\t{reference_value}")
