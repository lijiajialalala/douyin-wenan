#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _batch_common import build_batch_parser, print_batch_preview
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.config import load_runtime_config
from douyin_wenan.manifest.filters import select_txt_sync_pending, select_txt_sync_rebuildable
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema
from douyin_wenan.manifest.transitions import append_note, mark_txt_sync_failed, mark_txt_sync_succeeded, reset_dedup
from douyin_wenan.normalize.txt_writer import (
    build_standard_txt_path,
    is_runtime_transcript_path,
    render_standard_transcript,
    write_standard_transcript,
)
from douyin_wenan.pipeline.failures import hydrate_rows
from douyin_wenan.pipeline.preflight import assert_preflight, build_txt_sync_preflight


def parse_args():
    parser = build_batch_parser("Run the txt sync batch for ASR-complete rows.")
    parser.add_argument("--dry-run", action="store_true", help="Only preview eligible rows without writing txt files")
    parser.add_argument(
        "--rewrite-existing",
        action="store_true",
        help="Rebuild txt files for rows that already have ASR snapshots, even if txt_sync_status is already ok",
    )
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
    selected = (
        select_txt_sync_rebuildable(rows, limit=args.limit, author=args.author)
        if args.rewrite_existing
        else select_txt_sync_pending(rows, limit=args.limit, author=args.author)
    )
    if args.dry_run:
        stage = "txt_sync_rewrite" if args.rewrite_existing else "txt_sync"
        print_batch_preview(stage=stage, manifest_path=manifest_path, rows=selected, reference_field="asr_text_path")
        return 0
    if hydration_changed:
        repo.save_rows(rows)

    succeeded = 0
    failed = 0
    for row in selected:
        original_row = dict(row)
        row_copy = dict(row)
        try:
            transcript_text = Path(row_copy["asr_text_path"]).read_text(encoding="utf-8")
            previous_txt_path = (row_copy.get("txt_path", "") or "").strip()
            output_path = build_standard_txt_path(
                corpus_root=config.corpus_dir,
                author=row_copy["author"],
                work_id=row_copy["work_id"],
                title=row_copy["title"],
                existing_txt_path=previous_txt_path,
            )
            content = render_standard_transcript(row_copy, transcript_text)
            write_standard_transcript(output_path=output_path, content=content)
            reset_dedup(row_copy, reason="txt rebuilt from asr_text_path")
            _cleanup_superseded_generated_txts(
                author_dir=config.corpus_dir / row_copy["author"] / "transcripts",
                corpus_root=config.corpus_dir,
                work_id=row_copy["work_id"],
                canonical_path=output_path,
            )
            mark_txt_sync_succeeded(row_copy, txt_path=str(output_path.resolve()), note="txt synced from asr_text_path")
            repo.upsert_row(row_copy)
            succeeded += 1
            print(f"ok\t{row_copy['work_id']}\t{output_path}")
        except Exception as exc:
            failure_row = dict(original_row)
            if args.rewrite_existing and (original_row.get("txt_sync_status", "") or "").strip() == "ok":
                append_note(failure_row, f"txt sync rewrite failed: {exc}")
            else:
                mark_txt_sync_failed(failure_row, reason=str(exc))
            repo.upsert_row(failure_row)
            failed += 1
            print(f"failed\t{row_copy['work_id']}\t{exc}")

    print(f"manifest_path={manifest_path}")
    print(f"selected={len(selected)}")
    print(f"succeeded={succeeded}")
    print(f"failed={failed}")
    return 0


def _cleanup_superseded_generated_txts(*, author_dir: Path, corpus_root: Path, work_id: str, canonical_path: Path) -> None:
    resolved_canonical = canonical_path.resolve(strict=False)
    resolved_author_dir = author_dir.resolve(strict=False)
    for candidate in author_dir.glob(f"{work_id}_*.txt"):
        resolved_candidate = candidate.resolve(strict=False)
        if resolved_candidate == resolved_canonical:
            continue
        if resolved_candidate.parent != resolved_author_dir:
            continue
        if not is_runtime_transcript_path(candidate, corpus_root=corpus_root):
            continue
        if candidate.exists():
            candidate.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
