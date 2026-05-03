# Taxonomy And Tagging

## Purpose

This document defines the shared taxonomy for corpus analysis and skill
distillation.

This document does not define reusable writing skills.
It defines the classification and routing vocabulary used by Phase 2 labels,
Phase 3 assets, and production composition.

A taxonomy tag is not a skill.
A layer is not a skill.
A style family is not an author imitation instruction.

## Depends On

- [phase1-overview.md](C:/projects/douyin-wenan/docs/architecture/phase1/phase1-overview.md)

## Used By

- [overview.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/overview.md)
- [phase2-evidence-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase2-evidence-model.md)
- [phase3-distillation-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase3-distillation-model.md)
- [composition-and-conflict-policy.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/composition-and-conflict-policy.md)
- [evidence_record_schema.yaml](C:/projects/douyin-wenan/schemas/evidence_record_schema.yaml)
- [skill_card_schema.yaml](C:/projects/douyin-wenan/schemas/skill_card_schema.yaml)
- [anti_skill_card_schema.yaml](C:/projects/douyin-wenan/schemas/anti_skill_card_schema.yaml)

The taxonomy exists to prevent two failure modes:

1. one giant universal writing system with no nuance
2. one isolated skill set per author with no reuse path

The model is intentionally layered and routed.

## Design Model

There are two kinds of dimensions:

### Vertical Layers

These define where a rule belongs.

1. `general`
2. `content_type`
3. `style_family`
4. `author_signature`

### Horizontal Routing Dimensions

These define when a rule should be selected.

1. `goal`
2. `format`
3. `domain`

This means a final writing plan is never derived from one author alone.
It is composed from:

`layered rules + routing conditions`

## Vertical Layers

### 1. `general`

Purpose:
- cross-author fundamentals that remain useful in many settings

Examples:
- opening should establish object, problem, or payoff quickly
- argument progression should not stall
- ending should not detach from the body

Must not contain:
- one author's catchphrase
- one format's fixed round structure

### 2. `content_type`

Purpose:
- rules tied to the knowledge task the content is performing

Starter content types:

- `concept_explainer`
- `argument_breakdown`
- `book_digest`
- `historical_interpretation`
- `myth_narrative`
- `case_recap`
- `comparison_review`
- `method_walkthrough`

Examples:
- a `book_digest` often needs thesis, structure, and why-it-matters moves
- a `historical_interpretation` often needs timeline anchoring and causal claims

### 3. `style_family`

Purpose:
- rhetorical motion or delivery style shared by many authors

Starter style families:

- `question_hook`
- `strong_claim`
- `cold_explainer`
- `one_breath_deep_dive`
- `story_led`
- `debate_referee`
- `contrarian_reframe`

Examples:
- `question_hook` starts from audience doubt
- `strong_claim` starts from assertive framing

### 4. `author_signature`

Purpose:
- patterns that are meaningfully tied to one author

Examples:
- fixed opening phrase
- signature pacing move
- recurring turn-of-phrase
- recurring closing habit

Author signatures are not default global skills.
They are local overlays with narrow reuse value.

## Horizontal Routing Dimensions

### `goal`

The production objective.

Starter goals:

- `completion`
- `interaction`
- `save`
- `follow`
- `conversion`
- `authority`

Rows may carry one primary goal and up to two secondary goals.

### `format`

The delivery shape as seen by the viewer.

Starter formats:

- `short_monologue`
- `long_explainer`
- `dialogue`
- `debate_showdown`
- `list_countdown`
- `storytelling`
- `case_walkthrough`
- `qa_response`

`format` is not the same as `content_type`.
One content type can appear in many formats.

### `domain`

The subject area.

Starter domains:

- `ai`
- `history`
- `philosophy`
- `cognition`
- `books`
- `politics`
- `business`
- `science`

Rows may carry one primary domain and optional secondary domains.

## Tagging Rules

### Rule 1: exactly one primary `content_type`

Every row must resolve to one primary content type.
If a row appears mixed, choose the dominant knowledge task.

### Rule 2: exactly one primary `format`

Choose the form the audience experiences, not the topic.

### Rule 3: exactly one primary `domain`

Secondary domains are allowed, but only one primary domain.

### Rule 4: one primary `goal`

Goal must represent the strongest expected operator objective, not every
possible benefit.

### Rule 5: one primary `style_family`

A secondary style family may be attached only if it clearly coexists.

### Rule 6: zero or more `author_signature` tags

These are optional and should be sparse.
If every local habit becomes a signature tag, the label system loses value.

## Tagging Decision Order

When a row is ambiguous, classify in this order:

1. `format`
2. `content_type`
3. `domain`
4. `goal`
5. `style_family`
6. `author_signature`

This order matters because:

- format is usually easiest to observe
- content type depends on the task performed by the script
- style is often confused with surface wording

## Boundary Rules

### `content_type` versus `format`

Example:

- `AI showdown between two tools`
  - `content_type = comparison_review`
  - `format = debate_showdown`
  - `domain = ai`

### `style_family` versus `author_signature`

Example:

- “ask the audience a question at the opening” can be `style_family`
- one exact phrase repeated by one creator is `author_signature`

### `general` versus `content_type`

Example:

- “introduce the subject before the body” is `general`
- “anchor the era and causal claim in the first segment” belongs to
  `historical_interpretation`

## Tagging Quality Standards

Tags must be based on observable evidence.
They must not be assigned from vague vibe judgment alone.

Each label source should be classed as one of:

- `rule_based`
- `human_reviewed`
- `model_assisted`

Rows with weak transcript quality should not drive high-confidence tags.

## Relationship To Distillation

Layers are containers, not single skills.

Examples:

- `general` can contain dozens of positive and negative cards
- `content_type = concept_explainer` can contain multiple structure and pacing
  cards
- one `style_family` can contain opening, transition, and close cards

The taxonomy routes which cards are allowed to enter the same composition.

## Naming Rules

Use stable machine-friendly identifiers in data artifacts:

- `question_hook`
- `debate_showdown`
- `historical_interpretation`

Use human-friendly labels only in presentation layers.

## Initial Scope Rule

The starter vocabulary should stay deliberately narrow.
Do not explode the taxonomy on day one.

Add a new tag only when:

1. it changes behavior or analysis materially
2. it cannot be represented by an existing tag combination
3. it appears often enough to matter

## Document Authority

This document owns taxonomy truth.

Future card schemas, evidence records, and analysis scripts must reference this
taxonomy rather than inventing private tag lists.
