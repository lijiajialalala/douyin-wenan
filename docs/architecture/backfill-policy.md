# Backfill Policy

## Purpose

This document defines how legacy transcript txt files are converted into
manifest rows during Phase 1.

The existing corpus predates the new repository and contains mixed provenance:

- some rows were filled by SiliconFlow
- some rows were locally transcribed
- some rows may have been manually edited
- some rows may have incomplete upstream asset history

Because of that, backfill must be conservative. The policy should prefer
leaving a field empty or `pending` rather than pretending certainty.

Backfill now treats the legacy corpus as read-only input, not as the runtime
corpus output.

## Backfill Scope

Phase 1 backfill is limited to:

- reading standardized transcript txt files
- extracting trusted metadata from txt headers
- deriving a stable manifest row
- upserting that row into manifest

Backfill does not:

- recreate raw media assets
- guarantee that original video/audio still exists
- infer analysis-layer labels
- infer content type
- infer dedup classification

## Source of Truth During Backfill

During backfill, the source of truth is:

1. standardized transcript txt file content
2. the file path itself
3. explicit metadata lines inside the txt header

External reports are secondary references only. They must not override a valid
txt header unless we later add an explicit refresh mode.

## Stable Key Strategy

The row key must be chosen in this order:

### Preferred

1. extract Douyin video ID from `视频链接`

### Fallback

2. derive a synthetic ID from:
   - author
   - publish time
   - title
   - short link hash

### Rule

If a better key is discovered later, migration must be explicit. Phase 1
backfill must not silently rewrite existing `work_id` values in place without a
migration step.

## Field Trust Levels

Fields are not equally trustworthy during backfill.

## Level A: trusted from txt header

If present, these fields can be copied directly:

- `author`
- `platform`
- `account_link`
- `video_link`
- `title`
- `publish_time`
- `duration_text`
- `likes`
- `comments`
- `favorites`
- `shares`
- `followers`

## Level B: trusted after normalization or parsing

These are derived from trusted fields:

- `work_id`
- `duration_seconds`
- `legacy_txt_path`

## Level C: inferred operational state

These are not copied blindly; they are assigned by policy:

- `download_status`
- `asr_status`
- `txt_sync_status`
- `dedup_status`
- `manual_reviewed`

## Level D: unknown unless explicitly evidenced

These stay empty during backfill unless the txt explicitly proves them:

- `raw_video_path`
- `raw_audio_path`
- `download_time`
- `asr_provider`
- `asr_model`
- `asr_time`
- `asr_quality_grade`
- `asr_quality_flags`
- `dedup_group_id`

## Phase 1 Default Backfill Rules

For every valid standardized transcript txt file:

### Always set

- identity fields
- source metadata fields when present
- `legacy_txt_path`
- `dedup_status = unknown`
- `manual_reviewed = no` unless explicit evidence says otherwise

### Usually set to `pending`

- `download_status = pending`
- `asr_status = pending`
- `txt_sync_status = pending`

Reason:
- existing transcript text proves we have landed text, but it does not always
  prove we still possess the raw asset or the exact ASR provenance in a way
  robust enough for the new state system

### Optional provenances

If the txt header clearly states something like:

- `整理状态：siliconflow 自动转写并清洗噪声，未人工校对`
- `ASR来源：...`
- `ASR质量等级：...`

then backfill may populate:

- `asr_provider`
- `asr_model` if explicit
- `manual_reviewed`
- `asr_quality_grade`

However, lifecycle status still remains conservative:

- `asr_status = pending`
- `txt_sync_status = pending`

Reason:

- the legacy file proves external text exists
- it does not prove that the new runtime corpus has been generated
- it does not prove that the upstream ASR stage is complete under the new system

## Upsert Rules

When a matching row already exists in manifest:

### Allowed updates

- fill empty metadata fields
- refresh `legacy_txt_path`
- append notes for provenance clarification

### Disallowed silent updates

- replacing a non-empty `work_id`
- overwriting stronger state with weaker inferred state
- clearing explicit ASR metadata without reason

## Conflict Resolution

If txt and existing manifest disagree:

### Prefer manifest when it contains stronger operational evidence

Examples:
- manifest already has `download_status = ok` and valid `raw_video_path`
- manifest already has explicit `asr_provider`, `asr_model`, `asr_time`

### Prefer txt when it contains authoritative content metadata

Examples:
- corrected title
- corrected publish time
- corrected account link

### On unresolved conflict

- keep the stronger existing value
- append a note
- do not guess

## Invalid or Partial TXT Files

If a txt file:

- lacks `视频链接`
- lacks title
- is not in standardized structure
- has no usable transcript body

then the backfill script should choose one of two actions:

1. skip row creation and record a warning
2. create a partial row only if stable identity can still be established

Phase 1 default should prefer:

- skip + log

unless the file is clearly a standardized transcript with minor metadata loss.

## Notes Policy

Backfill may append notes such as:

- `backfilled from legacy txt on 2026-05-01`
- `legacy txt indicated siliconflow provenance`
- `metadata conflict retained manifest value`

Notes must explain operator reasoning. They must not become hidden machine
state.

## Example Backfill Outcome

### Input

Legacy transcript txt with:

- valid title
- valid author
- valid video link
- valid standard transcript body
- `整理状态：siliconflow 自动转写并清洗噪声，未人工校对`

### Output row

- `work_id`: parsed from video link
- `author`: copied
- `video_link`: copied
- `title`: copied
- `txt_path`: set
- `legacy_txt_path`: set
- `manual_reviewed = no`
- `asr_provider = siliconflow` when parser can reliably normalize that value
- `download_status = pending`
- `asr_status = pending`
- `txt_sync_status = pending`
- `dedup_status = unknown`
- `notes = backfilled from legacy txt ...`

## Implementation Consequences

This document defines the minimum behavior for
[scripts/sync_existing_txt_to_manifest.py](C:/projects/douyin-wenan/scripts/sync_existing_txt_to_manifest.py):

1. parse standardized txt safely
2. derive a stable key
3. build a conservative row
4. upsert without duplicating rows
5. avoid claiming stronger lifecycle certainty than the source proves
