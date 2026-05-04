#!/usr/bin/env python3
from __future__ import annotations

from _batch_common import build_batch_parser, print_batch_preview
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.analysis.phase2 import analyze_phase2_rows, select_phase2_ready, write_phase2_exports
from douyin_wenan.config import load_runtime_config
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema


def parse_args():
    parser = build_batch_parser("Run Phase 2 analysis on transcript-complete rows.")
    parser.add_argument("--dry-run", action="store_true", help="Only preview eligible rows without writing analysis outputs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    manifest_path = args.manifest_path or config.manifest_path
    repo = ManifestRepository(manifest_path, load_manifest_schema())
    repo.migrate_to_schema()
    rows = repo.load_rows()
    selected = select_phase2_ready(rows, author=args.author, limit=args.limit)
    route_baseline_rows = select_phase2_ready(rows) if args.author.strip() else None

    if args.dry_run:
        print_batch_preview(stage="phase2", manifest_path=manifest_path, rows=selected, reference_field="txt_path")
        return 0

    result = analyze_phase2_rows(selected, route_baseline_rows=route_baseline_rows)
    target_authors = (args.author.strip(),) if args.author.strip() else None
    paths = write_phase2_exports(result, config.analysis_dir, target_authors=target_authors)

    print(f"manifest_path={manifest_path}")
    print(f"selected={len(selected)}")
    print(f"labels={paths['labels']}")
    print(f"baselines={paths['baselines']}")
    print(f"author_foundations={paths['author_foundations']}")
    print(f"route_foundations={paths['route_foundations']}")
    print(f"contrasts={paths['contrasts']}")
    print(f"evidence={paths['evidence']}")
    print(f"labeled_rows={len(result.labeled_rows)}")
    print(f"author_baselines={len(result.author_baselines)}")
    print(f"author_foundation_patterns={len(result.author_foundation_patterns)}")
    print(f"route_foundation_patterns={len(result.route_foundation_patterns)}")
    print(f"author_high_low={len(result.author_high_low)}")
    print(f"evidence_records={len(result.evidence_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
