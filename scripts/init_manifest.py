#!/usr/bin/env python3
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the live Douyin manifest file.")
    parser.add_argument("--config", type=Path, default=None, help="Path to local config yaml")
    parser.add_argument("--manifest-path", type=Path, default=None, help="Override manifest output path")
    parser.add_argument("--force", action="store_true", help="Overwrite existing manifest file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    manifest_path = args.manifest_path or config.manifest_path

    schema = load_manifest_schema()
    repo = ManifestRepository(manifest_path, schema)
    repo.init_empty(overwrite=args.force)
    repo.migrate_to_schema()

    print(manifest_path)
    print(f"initialized={'yes' if manifest_path.exists() else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
