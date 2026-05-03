#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _batch_common import build_batch_parser, print_batch_preview
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.common.text_io import parse_transcript_header
from douyin_wenan.config import load_runtime_config
from douyin_wenan.dedup.near import classify_against_existing
from douyin_wenan.manifest.filters import select_dedup_pending
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema
from douyin_wenan.manifest.transitions import mark_dedup_classification
from douyin_wenan.pipeline.failures import hydrate_rows


def parse_args():
    parser = build_batch_parser("Run duplicate classification for transcript-complete rows.")
    parser.add_argument("--dry-run", action="store_true", help="Only preview eligible rows without writing classifications")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    manifest_path = args.manifest_path or config.manifest_path
    repo = ManifestRepository(manifest_path, load_manifest_schema())
    repo.migrate_to_schema()
    rows, hydration_changed = hydrate_rows(repo.load_rows())
    selected = select_dedup_pending(rows, limit=args.limit, author=args.author)
    if args.dry_run:
        print_batch_preview(stage="dedup", manifest_path=manifest_path, rows=selected, reference_field="txt_path")
        return 0
    if hydration_changed:
        repo.save_rows(rows)

    all_texts: list[tuple[str, str]] = []
    for row in rows:
        txt_path = (row.get("txt_path", "") or "").strip()
        if not txt_path:
            continue
        try:
            _, body = parse_transcript_header(Path(txt_path))
        except Exception:
            continue
        all_texts.append((row["work_id"], body))

    succeeded = 0
    failed = 0
    for row in selected:
        row_copy = dict(row)
        try:
            _, body = parse_transcript_header(Path(row_copy["txt_path"]))
            decision = classify_against_existing(work_id=row_copy["work_id"], text=body, existing_items=all_texts)
            note = f"dedup {decision.status}"
            if decision.status in {"duplicate", "near_duplicate"} and decision.matched_work_id:
                note = f"dedup {decision.status} matched {decision.matched_work_id} similarity={decision.similarity:.4f}"
            mark_dedup_classification(
                row_copy,
                dedup_status=decision.status,
                dedup_group_id=decision.group_id,
                note=note,
            )
            repo.upsert_row(row_copy)
            succeeded += 1
            print(f"ok\t{row_copy['work_id']}\t{decision.status}\t{decision.group_id}")
        except Exception as exc:
            failed += 1
            print(f"failed\t{row_copy['work_id']}\t{exc}")

    print(f"manifest_path={manifest_path}")
    print(f"selected={len(selected)}")
    print(f"succeeded={succeeded}")
    print(f"failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
