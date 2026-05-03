#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

from _batch_common import build_batch_parser
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.config import load_runtime_config
from douyin_wenan.manifest.repository import ManifestRepository
from douyin_wenan.manifest.schema import load_manifest_schema


def parse_args():
    parser = build_batch_parser("Run the end-to-end author pipeline for one author.")
    parser.add_argument("--dry-run", action="store_true", help="Preview each stage without changing files")
    parser.add_argument("--skip-retries", action="store_true", help="Skip retry passes for failed download/asr rows")
    parser.add_argument(
        "--include-nonretryable",
        action="store_true",
        help="Include blocked or terminal failed rows in retry passes",
    )
    parser.add_argument(
        "--max-download-failure-count",
        type=int,
        default=2,
        help="Only auto-retry download failures below this failed-attempt threshold",
    )
    parser.add_argument(
        "--max-asr-failure-count",
        type=int,
        default=2,
        help="Only auto-retry ASR failures below this failed-attempt threshold",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.author.strip():
        raise ValueError("--author is required for run_author_pipeline.py")

    config = load_runtime_config(args.config)
    manifest_path = args.manifest_path or config.manifest_path
    common_args = _build_common_args(args=args, manifest_path=manifest_path)

    stages: list[tuple[str, list[str]]] = [
        ("download", ["scripts/run_download_batch.py", *common_args]),
    ]
    if not args.skip_retries:
        stages.append(
            (
                "download_retry",
                [
                    "scripts/run_download_batch.py",
                    *common_args,
                    "--retry-failed",
                    "--max-failure-count",
                    str(args.max_download_failure_count),
                    *([] if not args.include_nonretryable else ["--include-nonretryable"]),
                ],
            )
        )
    stages.append(("asr", ["scripts/run_asr_batch.py", *common_args]))
    if not args.skip_retries:
        stages.append(
            (
                "asr_retry",
                [
                    "scripts/run_asr_batch.py",
                    *common_args,
                    "--retry-failed",
                    "--max-failure-count",
                    str(args.max_asr_failure_count),
                    *([] if not args.include_nonretryable else ["--include-nonretryable"]),
                ],
            )
        )
    stages.extend(
        [
            ("txt_sync", ["scripts/run_txt_sync_batch.py", *common_args]),
            ("dedup", ["scripts/run_dedup_batch.py", *common_args]),
        ]
    )

    if args.dry_run:
        for _, stage_args in stages:
            stage_args.append("--dry-run")

    for stage_name, stage_args in stages:
        _run_stage(stage_name, stage_args)

    _print_summary(manifest_path=manifest_path, author=args.author)
    return 0


def _build_common_args(*, args, manifest_path: Path) -> list[str]:
    common_args = [
        "--author",
        args.author,
        "--manifest-path",
        str(manifest_path),
    ]
    if args.config is not None:
        common_args.extend(["--config", str(args.config)])
    if args.limit > 0:
        common_args.extend(["--limit", str(args.limit)])
    if args.skip_preflight:
        common_args.append("--skip-preflight")
    return common_args


def _run_stage(stage_name: str, stage_args: list[str]) -> None:
    print(f"\n== {stage_name} ==")
    completed = subprocess.run([sys.executable, *stage_args], check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _print_summary(*, manifest_path: Path, author: str) -> None:
    repo = ManifestRepository(manifest_path, load_manifest_schema())
    repo.migrate_to_schema()
    rows = [row for row in repo.load_rows() if (row.get("author", "") or "").strip() == author.strip()]
    print("\n== summary ==")
    print(f"author={author}")
    print(f"rows={len(rows)}")
    for field in ["download_status", "asr_status", "txt_sync_status", "dedup_status"]:
        counts = Counter((row.get(field, "") or "").strip() for row in rows)
        counts_text = ", ".join(f"{name or '<blank>'}:{count}" for name, count in sorted(counts.items()))
        print(f"{field}={counts_text}")


if __name__ == "__main__":
    raise SystemExit(main())
