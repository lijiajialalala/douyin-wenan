# Composition And Conflict Policy

## Purpose

This document defines how Phase 3 assets are selected, combined, and resolved
when they conflict.

Without an explicit policy, the system will degrade into uncontrolled prompt
stacking.

## Depends On

- [overview.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/overview.md)
- [taxonomy-and-tagging.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/taxonomy-and-tagging.md)
- [phase3-distillation-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase3-distillation-model.md)
- [composition_plan_schema.yaml](C:/projects/douyin-wenan/schemas/composition_plan_schema.yaml)

## Used By

- [examples/composition_plan.example.yaml](C:/projects/douyin-wenan/examples/composition_plan.example.yaml)

## Core Principle

Conflict resolution must be structural.
It must not depend on the operator remembering which card should “probably win”.

## Composition Inputs

A composition request should specify:

- `domain`
- `format`
- `goal`
- `content_type`
- optional `style_family`
- optional `author_signature`
- factual inputs for the current topic

These are selection inputs, not generated outputs.

## Card Classes

For conflict purposes, cards should be treated as one of these classes:

1. `guardrail`
2. `structure`
3. `objective`
4. `style`
5. `signature`
6. `general_default`

The card class is derived from:

- layer
- card type
- routing scope

## Priority Order

Default precedence order:

1. `guardrail`
2. domain facts
3. `format` and structure rules
4. `goal` rules
5. `style_family` rules
6. `author_signature` overlays
7. `general` fallback defaults

This means:

- factual and safety constraints outrank stylistic preferences
- format structure outranks one creator's habits
- signatures decorate, but do not override the base production contract

## Hardness Levels

Every reusable asset must declare one of:

- `required`
- `preferred`
- `optional`

### `required`

Must be preserved unless blocked by a higher-priority required rule.

### `preferred`

Should be used if compatible with stronger cards.

### `optional`

May be dropped with no conflict escalation.

## Slot Model

To avoid vague overlap, cards should declare which script slot they affect.

Starter slots:

- `hook`
- `setup`
- `claim`
- `comparison`
- `example`
- `transition`
- `reframe`
- `close`
- `cta`

Two cards may coexist only if they do not require incompatible behavior in the
same slot, or if one explicitly overrides the other.

## Conflict Types

### 1. Structural Conflict

Example:
- `debate_showdown` requires explicit sides and rounds
- a slow narrative opener delays the conflict for too long

Resolution:
- structure wins

### 2. Pacing Conflict

Example:
- one card wants long setup
- another requires fast hook payoff

Resolution:
- the stronger slot owner wins
- preferred pacing cards may be downgraded or dropped

### 3. Voice Conflict

Example:
- one style card demands cold analytic tone
- one author signature demands teasing provocation

Resolution:
- if the voice conflict harms the declared goal or format, signature loses

### 4. Claim-Strength Conflict

Example:
- one domain requires careful uncertainty
- one style family pushes aggressive certainty

Resolution:
- factual guardrail wins

### 5. CTA Conflict

Example:
- one conversion card asks for direct follow
- one authority card discourages abrupt CTA

Resolution:
- goal-specific CTA wins if compatible with brand guardrails
- otherwise defer to softer authority-preserving CTA

## Specificity Rule

When two cards of the same class and hardness conflict:

1. the more specific card wins
2. if specificity is tied, the higher priority value wins
3. if still tied, prefer the card with stronger evidence grade
4. if still tied, reject the composition and require human review

Specificity order:

`author_signature > style_family > content_type > general`

But specificity never beats a higher-priority class.

## Incompatibility Rule

Cards must be allowed to declare:

- `depends_on`
- `overrides`
- `incompatible_with`

If a required card is incompatible with another required card at the same
priority class, the composition must fail closed and request review.

## Composition Procedure

Recommended order:

1. load domain facts and guardrails
2. select format and content-type structure cards
3. apply goal cards
4. apply style-family cards
5. attach optional author-signature overlays
6. run slot-level conflict detection
7. emit resolved composition plan

The output is a plan, not the final script yet.

## Resolved Composition Plan

The composition result should contain:

- selected card IDs
- dropped card IDs
- override decisions
- unresolved conflicts if any
- slot ownership map

This makes the assembly auditable.

Minimum serialized shape:

```yaml
composition_id: comp_001
input:
  domain: history
  format: long_explainer
  goal: completion
  content_type: historical_interpretation
  style_family: story_led
selected_cards:
  - historical_timeline_anchor
  - long_explainer_reanchor_thesis
  - story_led_scene_opening
dropped_cards:
  - author_signature_slow_warmup
override_decisions:
  - slot: hook
    winner: historical_timeline_anchor
    dropped: author_signature_slow_warmup
    reason: format structure requires early conflict setup
slot_ownership:
  hook: historical_timeline_anchor
  setup: story_led_scene_opening
  claim: historical_timeline_anchor
  close: long_explainer_reanchor_thesis
status: resolved
```

## Example: `AI` Debate Showdown

Input:

- `domain = ai`
- `format = debate_showdown`
- `goal = interaction`
- `content_type = comparison_review`
- `style_family = strong_claim`
- optional `author_signature = slow_literary_setup`

Expected resolution:

- `debate_showdown` structure owns `hook`, `comparison`, and `close`
- interaction goal owns CTA behavior
- strong-claim style may shape wording
- slow literary setup may only survive as optional seasoning

If the signature delays the conflict setup, it must be dropped.

## Failure Modes To Prevent

- stacking too many cards with no slot discipline
- letting style override fact constraints
- letting one creator's signature erase the declared format
- allowing unresolved conflicts to silently continue

## Initial Implementation Scope

At minimum, the first composition engine should support:

- slot ownership
- hardness handling
- explicit incompatibility lists
- override logging

Full automatic ranking can be added later.

## Exit Criteria

The policy is minimally usable once it can deterministically answer:

1. which class wins
2. which slot owns the instruction
3. which card gets dropped
4. when composition should fail and ask for review
