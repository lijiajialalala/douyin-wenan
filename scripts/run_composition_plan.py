#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import configure_stdio, ensure_src_path

ensure_src_path()
configure_stdio()

from douyin_wenan.analysis.composition import (
    CompositionRequest,
    compose_plan,
    default_composition_plan_path,
    load_anti_skill_cards,
    load_skill_cards,
    write_composition_plan,
)
from douyin_wenan.config import load_runtime_config


def parse_args():
    parser = argparse.ArgumentParser(description="Resolve a composition plan from Phase 3 assets.")
    parser.add_argument("--config", type=Path, default=None, help="Optional runtime config yaml path")
    parser.add_argument("--skill-dir", type=Path, default=None, help="Override skill card directory")
    parser.add_argument("--anti-skill-dir", type=Path, default=None, help="Override anti-skill card directory")
    parser.add_argument("--output-path", type=Path, default=None, help="Explicit composition output path")
    parser.add_argument("--domain", required=True, help="Primary domain routing input")
    parser.add_argument("--format", required=True, help="Primary format routing input")
    parser.add_argument("--goal", required=True, help="Primary goal routing input")
    parser.add_argument("--content-type", required=True, help="Primary content type routing input")
    parser.add_argument("--style-family", default="", help="Optional style-family routing input")
    parser.add_argument("--author-signature", default="", help="Optional author-signature routing input")
    parser.add_argument("--author-scope", default="", help="Optional author scope for author-local cards")
    parser.add_argument("--exclude-candidate", action="store_true", help="Only allow validated or active cards")
    parser.add_argument("--dry-run", action="store_true", help="Preview the resolved plan without writing YAML")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_runtime_config(args.config)
    skill_dir = args.skill_dir or (config.analysis_dir / "assets" / "skills")
    anti_skill_dir = args.anti_skill_dir or (config.analysis_dir / "assets" / "anti_skills")

    skill_cards = load_skill_cards(skill_dir)
    anti_skill_cards = load_anti_skill_cards(anti_skill_dir)
    plan = compose_plan(
        skill_cards,
        anti_skill_cards,
        CompositionRequest(
            domain=args.domain,
            format=args.format,
            goal=args.goal,
            content_type=args.content_type,
            style_family=args.style_family,
            author_signature=args.author_signature,
            author_scope=args.author_scope,
            allow_candidate=not args.exclude_candidate,
        ),
    )

    print(f"skill_dir={skill_dir}")
    print(f"anti_skill_dir={anti_skill_dir}")
    print(f"status={plan['status']}")
    print(f"selected_cards={len(plan.get('selected_cards', []))}")
    print(f"dropped_cards={len(plan.get('dropped_cards', []))}")
    print(f"slot_owners={len(plan.get('slot_ownership', {}))}")

    if args.dry_run:
        for slot, card_id in sorted(plan.get("slot_ownership", {}).items()):
            print(f"slot\t{slot}\t{card_id}")
        for conflict in plan.get("unresolved_conflicts", []):
            print(f"conflict\t{conflict}")
        return 0

    output_path = args.output_path or default_composition_plan_path(config.analysis_dir, plan)
    path = write_composition_plan(plan, output_path)
    print(f"output={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
