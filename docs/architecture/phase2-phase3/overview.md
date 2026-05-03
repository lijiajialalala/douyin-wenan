# Phase 2 And Phase 3 Overview

## Purpose

This document is the bridge between the corpus foundation and the reusable
writing asset system.

Phase 2 and Phase 3 are related, but they do not do the same job.

- Phase 2 produces evidence
- Phase 3 produces reusable assets from evidence
- composition consumes those assets under explicit conflict rules

## Depends On

- [phase1-overview.md](C:/projects/douyin-wenan/docs/architecture/phase1/phase1-overview.md)
- [runtime-layout.md](C:/projects/douyin-wenan/docs/architecture/phase1/runtime-layout.md)

## Used By

- [taxonomy-and-tagging.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/taxonomy-and-tagging.md)
- [phase2-evidence-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase2-evidence-model.md)
- [phase3-distillation-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase3-distillation-model.md)
- [composition-and-conflict-policy.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/composition-and-conflict-policy.md)

## System Flow

```text
phase1 corpus foundation
  -> phase2 row labels and evidence
  -> phase3 assets and cards
  -> composition plans
  -> production writing
```

## Responsibility Split

### Phase 2

Produces:

- row labels
- baselines
- contrasts
- evidence records

Does not produce:

- final reusable skill cards
- imitation instructions

### Phase 3

Produces:

- positive skill assets
- anti-skill assets
- conditional rule assets
- signature-pattern assets
- composition templates

Does not produce:

- unsupported causal claims
- uncontrolled author imitation

### Composition

Produces:

- resolved composition plans
- dropped-card decisions
- override decisions
- slot ownership maps

Does not produce:

- hidden prompt stacking
- silent conflict resolution by operator memory

## Document Map

- [taxonomy-and-tagging.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/taxonomy-and-tagging.md):
  classification and routing vocabulary
- [phase2-evidence-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase2-evidence-model.md):
  evidence production contract
- [phase3-distillation-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase3-distillation-model.md):
  asset production contract
- [composition-and-conflict-policy.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/composition-and-conflict-policy.md):
  composition and conflict rules

## Schema Map

- [evidence_record_schema.yaml](C:/projects/douyin-wenan/schemas/evidence_record_schema.yaml)
- [skill_card_schema.yaml](C:/projects/douyin-wenan/schemas/skill_card_schema.yaml)
- [anti_skill_card_schema.yaml](C:/projects/douyin-wenan/schemas/anti_skill_card_schema.yaml)
- [composition_plan_schema.yaml](C:/projects/douyin-wenan/schemas/composition_plan_schema.yaml)

## Example Map

- [evidence_record.example.yaml](C:/projects/douyin-wenan/examples/evidence_record.example.yaml)
- [skill_card.example.yaml](C:/projects/douyin-wenan/examples/skill_card.example.yaml)
- [anti_skill_card.example.yaml](C:/projects/douyin-wenan/examples/anti_skill_card.example.yaml)
- [composition_plan.example.yaml](C:/projects/douyin-wenan/examples/composition_plan.example.yaml)

## Design Boundary

This overview is intentionally the only new summary document for Phase 2 and
Phase 3.

Do not split `goal`, `format`, `domain`, or `style_family` into separate
architecture documents unless the existing taxonomy can no longer support the
system.
