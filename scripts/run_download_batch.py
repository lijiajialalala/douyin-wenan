#!/usr/bin/env python3
from __future__ import annotations

from _batch_common import build_batch_parser, print_batch_preview
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.config import load_runtime_config
from douyin_wenan.ingest.download import download_douyin_video
from douyin_wenan.manifest.filters import select_download_pending, select_download_retryable
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema
from douyin_wenan.manifest.transitions import mark_download_failed, mark_download_succeeded, reset_download
from douyin_wenan.pipeline.failures import classify_download_failure, hydrate_rows
from douyin_wenan.pipeline.preflight import assert_preflight, build_download_preflight


def parse_args():
    parser = build_batch_parser("Run the download batch for rows eligible to fetch raw video assets.")
    parser.add_argument("--dry-run", action="store_true", help="Only preview eligible rows without downloading")
    parser.add_argument("--retry-failed", action="store_true", help="Retry rows whose download_status is failed")
    parser.add_argument(
        "--include-nonretryable",
        action="store_true",
        help="Include blocked or terminal failed rows when retrying",
    )
    parser.add_argument(
        "--max-failure-count",
        type=int,
        default=2,
        help="Only auto-retry failed rows with fewer than this many failed batch attempts",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    manifest_path = args.manifest_path or config.manifest_path
    if not args.skip_preflight:
        assert_preflight(build_download_preflight(manifest_path=manifest_path, raw_video_dir=config.raw_video_dir))
    repo = ManifestRepository(manifest_path, load_manifest_schema())
    repo.migrate_to_schema()
    rows, hydration_changed = hydrate_rows(repo.load_rows())
    selected = (
        select_download_retryable(
            rows,
            limit=args.limit,
            author=args.author,
            max_failure_count=args.max_failure_count,
            include_nonretryable=args.include_nonretryable,
        )
        if args.retry_failed
        else select_download_pending(rows, limit=args.limit, author=args.author)
    )
    if args.dry_run:
        stage = "download_retry" if args.retry_failed else "download"
        print_batch_preview(stage=stage, manifest_path=manifest_path, rows=selected, reference_field="video_link")
        return 0
    if hydration_changed:
        repo.save_rows(rows)

    succeeded = 0
    failed = 0
    for row in selected:
        row_copy = dict(row)
        if args.retry_failed:
            reset_download(row_copy, reason="download retry requested")
        try:
            result = download_douyin_video(
                video_link=row_copy["video_link"],
                work_id=row_copy["work_id"],
                author=row_copy["author"],
                raw_video_dir=config.raw_video_dir,
            )
            mark_download_succeeded(
                row_copy,
                raw_video_path=str(result.output_path.resolve()),
                note=f"downloaded {result.bytes_written} bytes",
            )
            repo.upsert_row(row_copy)
            succeeded += 1
            print(f"ok\t{row_copy['work_id']}\t{result.output_path}")
        except Exception as exc:
            failure_row = dict(row_copy)
            failure = classify_download_failure(exc)
            mark_download_failed(
                failure_row,
                reason=str(exc),
                failure_class=failure.failure_class,
                failure_code=failure.failure_code,
            )
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
