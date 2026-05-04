# Phase 3 Distillation Model

## Purpose

Phase 3 converts structured evidence into reusable writing assets.

Its job is not to summarize authors.
Its job is to produce reusable, bounded, testable assets that can support
production writing later.

Phase 3 answers:

- what should we learn
- what should we avoid
- what only works under certain conditions
- what is merely one author's signature
- how multiple assets should be assembled into production templates

## Depends On

- [overview.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/overview.md)
- [taxonomy-and-tagging.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/taxonomy-and-tagging.md)
- [phase2-evidence-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase2-evidence-model.md)
- [skill_card_schema.yaml](C:/projects/douyin-wenan/schemas/skill_card_schema.yaml)
- [anti_skill_card_schema.yaml](C:/projects/douyin-wenan/schemas/anti_skill_card_schema.yaml)

## Used By

- [composition-and-conflict-policy.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/composition-and-conflict-policy.md)
- [examples/skill_card.example.yaml](C:/projects/douyin-wenan/examples/skill_card.example.yaml)
- [examples/anti_skill_card.example.yaml](C:/projects/douyin-wenan/examples/anti_skill_card.example.yaml)

## Core Principle

Not every repeated pattern becomes a skill.

Distillation must classify each candidate into one of several asset kinds rather
than forcing everything into “skill”.

The Phase 3 contract is:

`structured evidence -> candidate assets -> validation review -> active assets`

## Asset Versus Card

An asset is the conceptual unit.
A card is the serialized implementation unit.

Examples:

- `positive skill` is an asset kind
- `skill_card_schema.yaml` defines one card format
- a composition template is an asset kind
- a stored composition plan example is a serialized implementation artifact

This distinction prevents later mixing of:

- skill
- asset
- candidate asset
- skill card
- composition template
- rule

## Asset Kinds

### 1. Positive Skill

A reusable ability worth learning and reusing.

Examples:

- establish a concrete audience problem in the opening
- define debate rules before comparison rounds begin
- re-anchor the thesis every 60 to 90 seconds in long explainer formats

### 2. Anti-Skill

A repeated failure pattern worth explicitly avoiding.

Examples:

- long warm-up before conflict appears
- high emotion without argument progression
- detached CTA that does not emerge from the body

### 3. Conditional Rule

A rule that should only be activated when its scope conditions are satisfied.

Examples:

- strong-claim openings work better in confrontation-oriented formats than in
  gentle companion formats
- aggressive CTA may serve conversion goals but damage authority goals

### 4. Signature Pattern

A creator-linked trait that should be cataloged but not treated as a general
global asset.

Examples:

- one exact opening phrase
- one creator's recurring cadence pattern

### 5. Composition Template

A higher-level reusable assembly of cards for one production scenario.

Examples:

- `domain=ai + format=debate_showdown + goal=interaction`
- `domain=philosophy + format=long_explainer + goal=save`

## What A Skill Is

A Phase 3 skill must satisfy all of these:

1. reusable across more than one row
2. bounded by clear scope
3. explicit about when to use it
4. explicit about how to execute it
5. explicit about what output should change
6. grounded in traceable evidence

If a pattern fails these tests, it stays as an observation or signature note.

## Distillation Gates

Every candidate asset must pass these gates before activation.

### Gate 1: Evidence Threshold

The candidate must cite evidence records, not raw memory.

Minimum expectation:

- `E2` for narrow signature notes
- `E3` for reusable skill or anti-skill activation
- `E3` plus contradiction review for composition templates

### Gate 2: Scope Definition

The candidate must state:

- applicable layers
- routing conditions
- incompatible conditions

### Gate 3: Positive Or Negative Resolution

The candidate must explicitly answer whether it is:

- something to do
- something to avoid
- something conditional
- something signature-only

### Gate 4: Execution Contract

The candidate must include:

- required inputs
- steps
- output expectation
- evaluation checks

### Gate 5: Example Pair

The candidate must include:

- at least one positive example
- at least one counter-example or failure example

## Distillation Lifecycle

Suggested statuses:

- `candidate`
- `validated`
- `active`
- `deprecated`

Status is part of the asset definition.
It is not freeform note text.

## Transfer Boundary

Every card must state how far it can travel.

Phase 3 must not assume that a useful pattern is globally reusable. A card can
only be promoted as far as its evidence supports.

Required boundary fields:

- `transferability_level`: what kind of reuse the card supports
- `promotion_status`: how far the evidence has validated it
- `misuse_risks`: what can go wrong if the card is copied into the wrong route

Current transferability levels:

- `general_guardrail`: broad viewing or writing constraint
- `cross_domain_rhetorical`: rhetorical move that has cross-route support
- `format_specific`: tied primarily to format structure
- `content_type_specific`: tied primarily to content task
- `domain_specific`: tied primarily to domain material
- `author_signature_overlay`: author flavor, not a structure rule

Current promotion statuses:

- `author_local`: only supported inside the source author or source sample
- `route_validated`: supported inside a comparable route
- `cross_route_validated`: supported across multiple routes or authors
- `global_guardrail`: broad guardrail with strong evidence

This keeps Phase 3 from turning a historical narration habit, an AI showdown
move, or a creator signature into a fake universal writing rule.

## Layering Rule

Layers are containers for many assets.

Examples:

- `general` can hold several opening, pacing, logic, and ending assets
- one `content_type` can hold structure and example-use assets
- one `style_family` can hold tone and transition assets

The system must never assume:

`one layer = one skill`

## Required Fields For Reusable Assets

The exact field truth lives in:

- [skill_card_schema.yaml](C:/projects/douyin-wenan/schemas/skill_card_schema.yaml)
- [anti_skill_card_schema.yaml](C:/projects/douyin-wenan/schemas/anti_skill_card_schema.yaml)

At minimum, every reusable asset needs:

- stable ID
- title
- card kind
- layer
- routing tags
- transferability level
- promotion status
- misuse risks
- priority
- hardness
- trigger conditions
- avoid conditions
- execution steps or prevention steps
- evaluation checks
- evidence references

## Signature Handling Rule

Author signatures are valid outputs, but they are not default reusable skills.

They should be used for:

- recognition
- selective adaptation
- style-layer experiments

They should not bypass stronger structure or evidence rules.

## Relationship To Phase 2

Phase 3 must never skip the evidence layer.

The input sequence is:

1. labeled rows
2. grouped contrasts
3. evidence records
4. distillation candidate
5. asset validation

This prevents the common failure mode where a model sees a few good videos and
hallucinates broad writing principles.

## Distillation Outcomes By Evidence Strength

### `E0-E1`

Allowed outcomes:

- observation notes
- early signature notes

Not allowed:

- active global skill cards

### `E2`

Allowed outcomes:

- candidate conditional rules
- candidate author-signature overlays

### `E3-E4`

Allowed outcomes:

- active positive skill cards
- active anti-skill cards
- reusable composition templates

## Required Negative Output

Phase 3 must always emit both:

- what to learn
- what to avoid

If distillation only emits positive skills, it is incomplete.
Competitor corpora contain many seductive but low-transfer patterns.

## Composition Templates

Templates are not raw scripts.
They are orchestrated assemblies of cards chosen by:

- domain
- format
- goal
- content type
- style family
- optional author signature overlay

Their conflict rules are governed by
[composition-and-conflict-policy.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/composition-and-conflict-policy.md).

## Initial Implementation Scope

Phase 3 should start with:

- positive skill cards
- anti-skill cards
- conditional rule cards recorded with the same base skill schema

Signature notes and composition templates can follow once Phase 2 evidence is
stable.

## Exit Criteria

Phase 3 is minimally ready once it can:

- accept structured evidence references
- produce at least one positive skill card
- produce at least one anti-skill card
- mark one candidate as rejected due to weak evidence

Phase 3 is composition-ready once:

- routing tags are stable
- card hardness is explicit
- incompatibilities are recorded
- evaluation checks are attached
