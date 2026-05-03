#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _batch_common import build_batch_parser, print_batch_preview
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.config import load_runtime_config
from douyin_wenan.manifest.filters import (
    select_asr_completed,
    select_asr_pending,
    select_asr_reprocessable,
    select_asr_retryable,
)
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema
from douyin_wenan.manifest.transitions import (
    append_note,
    mark_asr_failed,
    mark_asr_refreshed,
    mark_asr_recleaned,
    mark_asr_succeeded,
    reset_asr,
)
from douyin_wenan.pipeline.failures import classify_asr_failure, hydrate_rows
from douyin_wenan.pipeline.preflight import assert_preflight, build_asr_preflight
from douyin_wenan.transcribe.postprocess import build_transcript_artifact_paths, process_transcript_text
from douyin_wenan.transcribe.quality import grade_transcript


def parse_args():
    parser = build_batch_parser("Run the ASR batch for rows with downloaded raw video assets.")
    parser.add_argument("--dry-run", action="store_true", help="Only preview eligible rows without transcribing")
    parser.add_argument(
        "--reclean-existing",
        action="store_true",
        help="Re-clean existing ASR text snapshots and refresh downstream state without calling the ASR API",
    )
    parser.add_argument(
        "--rerun-existing",
        action="store_true",
        help="Re-run ASR from raw video for rows already marked as ASR-complete and rebuild transcript outputs",
    )
    parser.add_argument("--retry-failed", action="store_true", help="Retry rows whose asr_status is failed")
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
        assert_preflight(
            build_asr_preflight(
                manifest_path=manifest_path,
                raw_audio_dir=config.raw_audio_dir,
                asr_text_dir=config.asr_text_dir,
                api_key_env=config.asr_api_key_env,
                require_api_key=not args.reclean_existing,
                require_ffmpeg=not args.reclean_existing,
                correction_api_key_env=config.text_correction_api_key_env,
                require_correction_api_key=config.text_correction_enabled,
            )
        )
    repo = ManifestRepository(manifest_path, load_manifest_schema())
    repo.migrate_to_schema()
    rows, hydration_changed = hydrate_rows(repo.load_rows())
    if args.reclean_existing and args.retry_failed:
        raise ValueError("--reclean-existing and --retry-failed cannot be used together")
    if args.rerun_existing and args.retry_failed:
        raise ValueError("--rerun-existing and --retry-failed cannot be used together")
    if args.rerun_existing and args.reclean_existing:
        raise ValueError("--rerun-existing and --reclean-existing cannot be used together")

    if args.rerun_existing:
        selected = select_asr_reprocessable(rows, limit=args.limit, author=args.author)
    elif args.reclean_existing:
        selected = select_asr_completed(rows, limit=args.limit, author=args.author)
    elif args.retry_failed:
        selected = select_asr_retryable(
            rows,
            limit=args.limit,
            author=args.author,
            max_failure_count=args.max_failure_count,
            include_nonretryable=args.include_nonretryable,
        )
    else:
        selected = select_asr_pending(rows, limit=args.limit, author=args.author)
    if args.dry_run:
        reference_field = "asr_text_path" if args.reclean_existing else "raw_video_path"
        if args.rerun_existing:
            stage = "asr_rerun"
        elif args.reclean_existing:
            stage = "asr_reclean"
        elif args.retry_failed:
            stage = "asr_retry"
        else:
            stage = "asr"
        print_batch_preview(stage=stage, manifest_path=manifest_path, rows=selected, reference_field=reference_field)
        return 0
    if hydration_changed:
        repo.save_rows(rows)

    api_key = ""
    if not args.reclean_existing:
        from douyin_wenan.transcribe.siliconflow import require_api_key

        api_key = require_api_key(config.asr_api_key_env)
    correction_api_key = ""
    if config.text_correction_enabled:
        from douyin_wenan.transcribe.openai_correction import require_api_key

        correction_api_key = require_api_key(config.text_correction_api_key_env)

    succeeded = 0
    failed = 0
    for row in selected:
        original_row = dict(row)
        row_copy = dict(row)
        if args.retry_failed:
            reset_asr(row_copy, reason="asr retry requested")
        try:
            note = "asr response ok"
            raw_audio_path_value = ""
            raw_text = ""
            artifacts = build_transcript_artifact_paths(
                asr_text_dir=config.asr_text_dir,
                author=row_copy["author"],
                work_id=row_copy["work_id"],
            )
            if args.reclean_existing:
                raw_source_path_text = (row_copy.get("asr_raw_text_path", "") or "").strip() or (
                    row_copy.get("asr_text_path", "") or ""
                ).strip()
                if not raw_source_path_text:
                    raise ValueError("No existing ASR text source found for reclean")
                raw_text = Path(raw_source_path_text).read_text(encoding="utf-8")
                raw_audio_path_value = (row_copy.get("raw_audio_path", "") or "").strip()
                note = "existing asr text recleaned"
            else:
                from douyin_wenan.transcribe.audio import extract_audio_for_asr
                from douyin_wenan.transcribe.siliconflow import transcribe_audio_file

                raw_video_path = Path(row_copy["raw_video_path"])
                audio_path = extract_audio_for_asr(
                    raw_video_path=raw_video_path,
                    raw_audio_dir=config.raw_audio_dir,
                    author=row_copy["author"],
                    work_id=row_copy["work_id"],
                )
                transcript = transcribe_audio_file(
                    audio_path=audio_path,
                    api_key=api_key,
                    base_url=config.asr_base_url,
                    model=config.asr_model,
                )
                raw_text = transcript.text
                raw_audio_path_value = str(audio_path.resolve())
                note = f"asr response {transcript.response_id or 'ok'}"

            correction_runner = None
            if config.text_correction_enabled:
                from douyin_wenan.transcribe.openai_correction import correct_transcript_text

                correction_runner = lambda normalized_text: correct_transcript_text(
                    transcript_text=normalized_text,
                    api_key=correction_api_key,
                    base_url=config.text_correction_base_url,
                    model=config.text_correction_model,
                    max_char_delta_ratio=config.text_correction_max_char_delta_ratio,
                    max_edit_count=config.text_correction_max_edit_count,
                )
            processed = process_transcript_text(
                raw_text=raw_text,
                raw_text_path=artifacts.raw_text_path,
                final_text_path=artifacts.final_text_path,
                correction_json_path=artifacts.correction_json_path if config.text_correction_enabled else None,
                correction_runner=correction_runner,
            )
            grade, flags, char_count, cpm_text = grade_transcript(
                processed.final_text,
                row_copy.get("duration_seconds", ""),
            )
            if args.reclean_existing:
                mark_asr_recleaned(
                    row_copy,
                    raw_audio_path=raw_audio_path_value,
                    asr_raw_text_path=str(artifacts.raw_text_path.resolve()),
                    asr_text_path=str(artifacts.final_text_path.resolve()),
                    asr_correction_json_path=processed.correction_json_path,
                    asr_char_count=char_count,
                    asr_chars_per_minute=cpm_text,
                    asr_quality_grade=grade,
                    asr_quality_flags=flags,
                    note=f"{note}; {processed.note}",
                )
            elif args.rerun_existing:
                mark_asr_refreshed(
                    row_copy,
                    raw_audio_path=raw_audio_path_value,
                    asr_raw_text_path=str(artifacts.raw_text_path.resolve()),
                    asr_text_path=str(artifacts.final_text_path.resolve()),
                    asr_correction_json_path=processed.correction_json_path,
                    asr_provider=config.asr_provider,
                    asr_model=config.asr_model,
                    asr_char_count=char_count,
                    asr_chars_per_minute=cpm_text,
                    asr_quality_grade=grade,
                    asr_quality_flags=flags,
                    note=f"{note}; {processed.note}",
                )
            else:
                mark_asr_succeeded(
                    row_copy,
                    raw_audio_path=raw_audio_path_value,
                    asr_raw_text_path=str(artifacts.raw_text_path.resolve()),
                    asr_text_path=str(artifacts.final_text_path.resolve()),
                    asr_correction_json_path=processed.correction_json_path,
                    asr_provider=config.asr_provider,
                    asr_model=config.asr_model,
                    asr_char_count=char_count,
                    asr_chars_per_minute=cpm_text,
                    asr_quality_grade=grade,
                    asr_quality_flags=flags,
                    note=f"{note}; {processed.note}",
                )
            repo.upsert_row(row_copy)
            succeeded += 1
            print(f"ok\t{row_copy['work_id']}\t{artifacts.final_text_path}")
        except Exception as exc:
            failure_row = dict(original_row)
            if args.reclean_existing:
                append_note(failure_row, f"asr reclean failed: {exc}")
            elif args.rerun_existing:
                append_note(failure_row, f"asr rerun failed: {exc}")
            else:
                failure = classify_asr_failure(exc)
                mark_asr_failed(
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
