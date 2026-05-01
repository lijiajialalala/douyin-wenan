#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _batch_common import build_batch_parser, print_batch_preview
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.config import load_runtime_config
from douyin_wenan.manifest.filters import select_asr_completed, select_asr_pending
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema
from douyin_wenan.manifest.transitions import mark_asr_failed, mark_asr_succeeded, reset_txt_sync
from douyin_wenan.paths import ensure_parent_dir
from douyin_wenan.transcribe.audio import extract_audio_for_asr
from douyin_wenan.transcribe.cleaning import clean_transcript_text
from douyin_wenan.transcribe.quality import grade_transcript
from douyin_wenan.transcribe.siliconflow import require_api_key, transcribe_audio_file


def parse_args():
    parser = build_batch_parser("Run the ASR batch for rows with downloaded raw video assets.")
    parser.add_argument("--dry-run", action="store_true", help="Only preview eligible rows without transcribing")
    parser.add_argument(
        "--reclean-existing",
        action="store_true",
        help="Re-clean existing ASR text snapshots and refresh downstream state without calling the ASR API",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    manifest_path = args.manifest_path or config.manifest_path
    repo = ManifestRepository(manifest_path, load_manifest_schema())
    repo.migrate_to_schema()
    rows = repo.load_rows()
    selected = (
        select_asr_completed(rows, limit=args.limit, author=args.author)
        if args.reclean_existing
        else select_asr_pending(rows, limit=args.limit, author=args.author)
    )
    if args.dry_run:
        reference_field = "asr_text_path" if args.reclean_existing else "raw_video_path"
        stage = "asr_reclean" if args.reclean_existing else "asr"
        print_batch_preview(stage=stage, manifest_path=manifest_path, rows=selected, reference_field=reference_field)
        return 0

    api_key = ""
    if not args.reclean_existing:
        api_key = require_api_key(config.asr_api_key_env)

    succeeded = 0
    failed = 0
    for row in selected:
        row_copy = dict(row)
        try:
            note = "asr response ok"
            raw_audio_path_value = ""
            if args.reclean_existing:
                asr_text_path = Path(row_copy["asr_text_path"])
                cleaned_text = clean_transcript_text(asr_text_path.read_text(encoding="utf-8"))
                raw_audio_path_value = (row_copy.get("raw_audio_path", "") or "").strip()
                reset_txt_sync(row_copy, reason="asr text recleaned")
                note = "existing asr text recleaned"
            else:
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
                cleaned_text = clean_transcript_text(transcript.text)
                asr_text_path = config.asr_text_dir / row_copy["author"] / f"{row_copy['work_id']}.txt"
                ensure_parent_dir(asr_text_path)
                raw_audio_path_value = str(audio_path.resolve())
                note = f"asr response {transcript.response_id or 'ok'}"

            ensure_parent_dir(asr_text_path)
            asr_text_path.write_text(cleaned_text, encoding="utf-8")
            grade, flags, char_count, cpm_text = grade_transcript(cleaned_text, row_copy.get("duration_seconds", ""))
            mark_asr_succeeded(
                row_copy,
                raw_audio_path=raw_audio_path_value,
                asr_text_path=str(asr_text_path.resolve()),
                asr_provider=config.asr_provider,
                asr_model=config.asr_model,
                asr_char_count=char_count,
                asr_chars_per_minute=cpm_text,
                asr_quality_grade=grade,
                asr_quality_flags=flags,
                note=note,
            )
            repo.upsert_row(row_copy)
            succeeded += 1
            print(f"ok\t{row_copy['work_id']}\t{asr_text_path}")
        except Exception as exc:
            mark_asr_failed(row_copy, reason=str(exc))
            repo.upsert_row(row_copy)
            failed += 1
            print(f"failed\t{row_copy['work_id']}\t{exc}")

    print(f"manifest_path={manifest_path}")
    print(f"selected={len(selected)}")
    print(f"succeeded={succeeded}")
    print(f"failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
