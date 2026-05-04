#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _batch_common import build_batch_parser, print_batch_preview
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.common.text_io import compact_char_count, parse_transcript_header
from douyin_wenan.config import load_runtime_config
from douyin_wenan.manifest.filters import select_legacy_txt_pending
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema
from douyin_wenan.manifest.transitions import mark_txt_sync_failed, mark_txt_sync_succeeded, reset_dedup
from douyin_wenan.normalize.txt_writer import build_standard_txt_path, render_standard_transcript, write_standard_transcript
from douyin_wenan.pipeline.failures import hydrate_rows
from douyin_wenan.pipeline.preflight import assert_preflight, build_txt_sync_preflight


def parse_args():
    parser = build_batch_parser("Import legacy standardized txt files into the runtime corpus.")
    parser.add_argument("--dry-run", action="store_true", help="Only preview eligible rows without writing txt files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    manifest_path = args.manifest_path or config.manifest_path
    if not args.skip_preflight:
        assert_preflight(build_txt_sync_preflight(manifest_path=manifest_path, corpus_dir=config.corpus_dir))
    repo = ManifestRepository(manifest_path, load_manifest_schema())
    repo.migrate_to_schema()
    rows, hydration_changed = hydrate_rows(repo.load_rows())
    selected = select_legacy_txt_pending(rows, limit=args.limit, author=args.author)
    if args.dry_run:
        print_batch_preview(
            stage="legacy_txt",
            manifest_path=manifest_path,
            rows=selected,
            reference_field="legacy_txt_path",
        )
        return 0
    if hydration_changed:
        repo.save_rows(rows)

    succeeded = 0
    failed = 0
    for row in selected:
        original_row = dict(row)
        row_copy = dict(row)
        try:
            legacy_txt_path = Path((row_copy.get("legacy_txt_path", "") or "").strip())
            if not legacy_txt_path.exists():
                raise FileNotFoundError(f"legacy txt not found: {legacy_txt_path}")
            _, body = parse_transcript_header(legacy_txt_path)
            if compact_char_count(body) == 0:
                raise ValueError("legacy txt body is empty")
            output_path = build_standard_txt_path(
                corpus_root=config.corpus_dir,
                author=row_copy["author"],
                work_id=row_copy["work_id"],
                title=row_copy["title"],
                existing_txt_path=(row_copy.get("txt_path", "") or "").strip(),
            )
            content = render_standard_transcript(row_copy, body)
            write_standard_transcript(output_path=output_path, content=content)
            reset_dedup(row_copy, reason="txt imported from legacy_txt_path")
            mark_txt_sync_succeeded(
                row_copy,
                txt_path=str(output_path.resolve()),
                note="txt imported from legacy_txt_path",
            )
            repo.upsert_row(row_copy)
            succeeded += 1
            print(f"ok\t{row_copy['work_id']}\t{output_path}")
        except Exception as exc:
            failure_row = dict(original_row)
            mark_txt_sync_failed(failure_row, reason=str(exc))
            repo.upsert_row(failure_row)
            failed += 1
            print(f"failed\t{row_copy['work_id']}\t{exc}")

    print(f"manifest_path={manifest_path}")
    print(f"selected={len(selected)}")
    print(f"succeeded={succeeded}")
    print(f"failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
