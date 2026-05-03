# Phase 2 Evidence Model

## Purpose

Phase 2 converts transcript-complete corpus rows into structured evidence.
It is the analysis layer between the Phase 1 corpus foundation and the Phase 3
distillation layer.

Phase 2 must answer:

- what patterns appear in the corpus
- where those patterns appear
- how they relate to observable performance
- whether they hold within one author, across authors, or only in narrow scopes

Phase 2 must not answer:

- what we should blindly imitate
- what final skill card should be activated in production
- whether a pattern is desirable without evidence review

Those are Phase 3 responsibilities.

## Depends On

- [taxonomy-and-tagging.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/taxonomy-and-tagging.md)
- [phase1-overview.md](C:/projects/douyin-wenan/docs/architecture/phase1/phase1-overview.md)
- [runtime-layout.md](C:/projects/douyin-wenan/docs/architecture/phase1/runtime-layout.md)
- [evidence_record_schema.yaml](C:/projects/douyin-wenan/schemas/evidence_record_schema.yaml)

## Used By

- [overview.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/overview.md)
- [phase3-distillation-model.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/phase3-distillation-model.md)
- [examples/evidence_record.example.yaml](C:/projects/douyin-wenan/examples/evidence_record.example.yaml)

## Core Principle

Phase 2 emits evidence, not advice.

The contract is:

`phase1-complete corpus -> row labels -> aggregates -> contrasts -> evidence records`

No Phase 2 script may skip directly from transcript text to reusable skill cards.

## Evidence Is Not Causality

Evidence strength is not the same thing as proof of causal effect.

The following statements are not equivalent:

- a high-performing sample often contains a pattern
- the pattern caused the high performance
- the pattern will transfer across authors
- the pattern is worth learning in production

Phase 2 may support pattern candidacy.
It may not claim causal truth unless later validation exists outside this
documented pipeline.

## Inputs

Phase 2 only works on rows that are foundation-complete.

Minimum preconditions:

- `download_status == ok`
- `asr_status == ok`
- `txt_sync_status == ok`
- `dedup_status != unknown`

Required assets:

- manifest rows
- canonical transcript txt files
- source metadata already stored in manifest

Optional later inputs:

- manual quality review marks
- frame or cover analysis
- comment and follow conversion snapshots

Phase 2 starts as text-first. It should not wait for multimodal expansion.

## Outputs

Phase 2 outputs are runtime data under the configured `analysis_dir`.
They are not repository truth and are not committed to Git.

Recommended runtime subdirectories:

```text
analysis/
  labels/
  baselines/
  contrasts/
  evidence/
  exports/
```

Recommended artifacts:

- `labels/row_labels.csv`
- `baselines/author_baselines.csv`
- `baselines/content_type_baselines.csv`
- `contrasts/author_high_low.csv`
- `contrasts/cross_author_checks.csv`
- `evidence/evidence_records.csv`
- `exports/pattern_candidates.csv`

The canonical design truth for Phase 2 stays in this document and in:

- [taxonomy-and-tagging.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/taxonomy-and-tagging.md)
- [evidence_record_schema.yaml](C:/projects/douyin-wenan/schemas/evidence_record_schema.yaml)

## Relationship to Other Phases

### Upstream: Phase 1

Phase 1 gives Phase 2 stable rows and transcript assets.
Phase 2 must not recreate Phase 1 workflow state.

### Downstream: Phase 3

Phase 3 may only distill from structured evidence records.
It must not scrape raw transcript text directly as its primary input.

The handoff contract is:

`Phase 2 evidence record -> Phase 3 candidate asset`

## Evidence Units

Phase 2 should build evidence in ascending order of strength.

### 1. Observation

A single row-level note or label.

Examples:

- opening uses a direct question
- first strong claim appears after 18 seconds
- transcript contains three explicit examples

An observation is useful, but never sufficient for distillation.

### 2. Labeled Row

A row with structured tags and measured fields.

Examples:

- `content_type = concept_explainer`
- `format = long_explainer`
- `style_family = question_hook`
- `author_relative_percentile = 0.91`

### 3. Aggregate

A grouped statistical view.

Examples:

- average engagement band for `format = debate_showdown`
- median duration for `content_type = book_digest`
- opening pattern frequency by author

### 4. Contrast Finding

A comparison between meaningful groups.

Preferred contrast scopes:

- same author high vs low
- same content type across authors
- same format across domains
- same style family with different goals

### 5. Corroborated Pattern

A candidate pattern that survives more than one comparison scope.

Example:

- direct question openings appear more often in high performers within author
  and remain common in cross-author rows of the same format

### 6. Rejected Pattern

A pattern that looked plausible but failed support checks.

Rejected patterns are first-class evidence outputs.
They protect Phase 3 from cargo-cult distillation.

## Required Row Labels

Every row entering Phase 2 should receive a bounded label set.

### Routing Labels

- `content_type`
- `format`
- `domain`
- `primary_goal`

### Style Labels

- `style_family`
- optional secondary style family

### Structural Labels

- `hook_type`
- `opening_object_presence`
- `opening_problem_presence`
- `opening_payoff_presence`
- `argument_shape`
- `example_density_band`
- `cta_presence`
- `cta_type`

### Quality Labels

- `transcript_quality_gate`
- `manual_reviewed`
- `dedup_status`

The controlled vocabulary lives in
[taxonomy-and-tagging.md](C:/projects/douyin-wenan/docs/architecture/phase2-phase3/taxonomy-and-tagging.md).

## Performance Modeling

Phase 2 should not pretend that one global engagement score is the truth.
It should retain multiple performance views.

### Required Metrics

- raw likes
- raw comments
- raw favorites
- raw shares
- follower snapshot

### Derived Metrics

- `like_follower_ratio`
- `favorite_follower_ratio`
- `share_follower_ratio`
- `comment_follower_ratio`
- `composite_engagement_score_v1`

### Relative Metrics

These matter more than raw counts.

- `author_relative_percentile`
- `author_relative_band`
- `author_relative_zscore` when sample size permits
- `content_type_relative_percentile` later
- `format_relative_percentile` later

Phase 2 conclusions should prefer relative metrics over naked cross-author
counts.

## Confidence Grades

Each evidence record must carry a confidence grade.

### `E0`

Single observation only. No comparison support.

### `E1`

Repeated within a narrow local slice, but not contrasted against alternatives.

### `E2`

Supported by one meaningful contrast, usually within one author.

### `E3`

Supported by repeated contrasts in more than one scope.

### `E4`

Strongly corroborated across multiple scopes with low contradiction rate.

Phase 3 should not create reusable production assets from `E0` or `E1`
patterns except as explicit author-signature notes.

## Phase 2 Pipeline

Recommended bounded operations:

1. select eligible rows from manifest
2. parse canonical transcript headers and bodies
3. assign routing and structure labels
4. compute raw and relative performance fields
5. build author baselines
6. build author high-low contrasts
7. build cross-author corroboration checks
8. emit evidence records and candidate exports

Each operation should follow the same data-system contract as Phase 1:

`read stable inputs -> perform one bounded analysis job -> write standard output`

## Evidence Record Requirements

An evidence record must answer these questions:

1. what pattern is being described
2. in what scope it was observed
3. what supports it
4. what contradicts it
5. how strong the support is
6. whether it is ready for distillation review

See
[evidence_record_schema.yaml](C:/projects/douyin-wenan/schemas/evidence_record_schema.yaml).

## What Phase 2 Must Never Do

- emit direct “copy this author” recommendations as truth
- collapse all domains and formats into one average
- treat repeated frequency as proof of quality
- let author body size or follower base substitute for evidence
- skip rejected patterns

## Exit Criteria

Phase 2 is considered minimally ready once it can produce:

- one row-level label file
- one author baseline file
- one same-author high-low contrast file
- one evidence record export with confidence grades

Phase 2 is considered distillation-ready once:

- evidence confidence is attached
- contradiction counts are tracked
- ready-for-distillation flags are explicit
- no Phase 3 output depends on ad hoc human memory
