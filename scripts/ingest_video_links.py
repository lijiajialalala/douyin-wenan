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
from douyin_wenan.ingest.links import build_link_row, load_link_sources, merge_link_row
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest new Douyin source links into manifest.")
    parser.add_argument("--config", type=Path, default=None, help="Path to local config yaml")
    parser.add_argument("--manifest-path", type=Path, default=None, help="Override manifest file path")
    parser.add_argument("--input-file", type=Path, default=None, help="CSV or TSV with author,video_link,title columns")
    parser.add_argument("--author", type=str, default="", help="Single-row author")
    parser.add_argument("--video-link", type=str, default="", help="Single-row Douyin video link")
    parser.add_argument("--title", type=str, default="", help="Single-row title")
    parser.add_argument("--account-link", type=str, default="", help="Single-row account link")
    parser.add_argument("--publish-time", type=str, default="", help="Single-row publish time text")
    parser.add_argument("--duration-text", type=str, default="", help="Single-row duration text like 07:32")
    parser.add_argument("--notes", type=str, default="", help="Single-row notes text")
    return parser.parse_args()


def resolve_sources(args: argparse.Namespace) -> list[dict[str, str]]:
    if args.input_file:
        return load_link_sources(args.input_file)

    if not args.author or not args.video_link or not args.title:
        raise ValueError("Single-row ingest requires --author, --video-link, and --title")

    return [
        {
            "author": args.author,
            "video_link": args.video_link,
            "title": args.title,
            "account_link": args.account_link,
            "publish_time": args.publish_time,
            "duration_text": args.duration_text,
            "notes": args.notes,
        }
    ]


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    manifest_path = args.manifest_path or config.manifest_path

    schema = load_manifest_schema()
    repo = ManifestRepository(manifest_path, schema)
    repo.init_empty(overwrite=False)
    repo.migrate_to_schema()

    rows_by_work_id = repo.index_by("work_id")
    sources = resolve_sources(args)

    created = 0
    updated = 0
    for source in sources:
        incoming = build_link_row(source)
        work_id = incoming["work_id"]
        existing = rows_by_work_id.get(work_id)
        if existing is None:
            repo.upsert_row(incoming)
            rows_by_work_id[work_id] = incoming
            created += 1
            continue

        merged = merge_link_row(existing, incoming)
        repo.upsert_row(merged)
        rows_by_work_id[work_id] = merged
        updated += 1

    print(manifest_path)
    print(f"created={created}")
    print(f"updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
