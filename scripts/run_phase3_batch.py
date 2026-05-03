#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _batch_common import build_batch_parser
from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.analysis.phase3 import distill_phase3_cards, load_evidence_records_csv, write_phase3_exports
from douyin_wenan.config import load_runtime_config


def parse_args():
    parser = build_batch_parser("Run Phase 3 distillation from evidence records.")
    parser.add_argument(
        "--evidence-path",
        type=Path,
        default=None,
        help="Override evidence record csv path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview eligible evidence rows without writing cards")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    evidence_path = args.evidence_path or (config.analysis_dir / "evidence" / "evidence_records.csv")
    evidence_records = load_evidence_records_csv(evidence_path)
    result = distill_phase3_cards(evidence_records, author=args.author)

    if args.dry_run:
        print(f"evidence_path={evidence_path}")
        print(f"skill_cards={len(result.skill_cards)}")
        print(f"anti_skill_cards={len(result.anti_skill_cards)}")
        print(f"skipped_records={len(result.skipped_records)}")
        for card in result.skill_cards:
            print(f"skill\t{card['card_id']}\t{card['title']}")
        for card in result.anti_skill_cards:
            print(f"anti\t{card['card_id']}\t{card['title']}")
        return 0

    target_authors = (args.author.strip(),) if args.author.strip() else None
    paths = write_phase3_exports(result, config.analysis_dir, target_authors=target_authors)
    print(f"evidence_path={evidence_path}")
    print(f"skills={len(result.skill_cards)}")
    print(f"anti_skills={len(result.anti_skill_cards)}")
    print(f"skipped_records={len(result.skipped_records)}")
    print(f"skill_dir={paths['skills'][0].parent if paths['skills'] else config.analysis_dir / 'assets' / 'skills'}")
    print(
        f"anti_skill_dir={paths['anti_skills'][0].parent if paths['anti_skills'] else config.analysis_dir / 'assets' / 'anti_skills'}"
    )
    print(f"summary={paths['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
