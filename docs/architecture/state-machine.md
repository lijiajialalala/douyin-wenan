# State Machine

## Scope

This document defines the Phase 1 lifecycle for one work item. A work item is a
single Douyin video represented by one `work_id`.

## State Ownership

`douyin_manifest.csv` is the only workflow ledger.

Derived files such as transcript txt files, dedup reports, or analysis exports
must never become the source of workflow truth.

## Operating Model

Phase 1 is state-driven, not chain-driven.

The system should never assume:

`script A -> script B -> script C`

Instead each script must:

1. read rows from manifest
2. select rows whose current state matches its preconditions
3. perform one bounded action
4. write new state back to the same rows

This allows:

- reruns after partial failure
- idempotent recovery
- stage-specific retries
- future parallel execution

## Phase 1 States

### Download

- `pending`
- `ok`
- `failed`

### ASR

- `pending`
- `ok`
- `failed`

### TXT Sync

- `pending`
- `ok`
- `failed`

### Dedup

- `unknown`
- `unique`
- `near_duplicate`
- `duplicate`

## Stage Meaning

### `download_status`

| State | Meaning |
|---|---|
| `pending` | video not downloaded yet, or download explicitly reset |
| `ok` | video asset exists and was accepted by the system |
| `failed` | last download attempt failed |

### `asr_status`

| State | Meaning |
|---|---|
| `pending` | transcript not generated yet, or rerun requested |
| `ok` | transcript generated and ASR metadata recorded |
| `failed` | last ASR attempt failed |

### `txt_sync_status`

| State | Meaning |
|---|---|
| `pending` | transcript not landed to standard txt yet |
| `ok` | standard txt exists and manifest points to it |
| `failed` | landing or sync failed |

### `dedup_status`

| State | Meaning |
|---|---|
| `unknown` | dedup not evaluated yet |
| `unique` | accepted as unique analysis sample |
| `near_duplicate` | grouped with high-similarity items |
| `duplicate` | exact or near-exact duplicate excluded from primary analysis |

## Allowed Transitions

### Download

- `pending -> ok`
- `pending -> failed`
- `failed -> pending`

Disallowed:

- `ok -> failed` without an explicit reset event
- `ok -> pending` unless operator intentionally invalidates the asset

Typical triggers:

- `pending -> ok`: downloader succeeded, `raw_video_path` recorded
- `pending -> failed`: downloader failed and error is recorded in `notes`
- `failed -> pending`: retry requested

### ASR

- `pending -> ok`
- `pending -> failed`
- `failed -> pending`

Constraint:
- `asr_status` cannot become `ok` unless `download_status == ok`

Disallowed:

- `ok -> failed` without an explicit rerun event
- `ok -> pending` unless transcript is intentionally invalidated

Typical triggers:

- `pending -> ok`: transcript generated and quality fields computed
- `pending -> failed`: provider failed, transcript unusable, or audio missing
- `failed -> pending`: rerun requested after fixing provider or asset issue

### TXT Sync

- `pending -> ok`
- `pending -> failed`
- `failed -> pending`

Constraint:
- `txt_sync_status` cannot become `ok` unless `asr_status == ok`

Disallowed:

- `ok -> failed` without an explicit rerender event
- `ok -> pending` unless target txt is intentionally being regenerated

Typical triggers:

- `pending -> ok`: standard txt file created or updated successfully
- `pending -> failed`: parser / writer / path resolution failed
- `failed -> pending`: rerun requested

### Dedup

- `unknown -> unique`
- `unknown -> near_duplicate`
- `unknown -> duplicate`
- `unique -> near_duplicate`
- `near_duplicate -> unique`

Constraint:
- dedup is allowed only after transcript text exists in a standard txt path

Disallowed:

- `duplicate -> unique` without explicit re-evaluation
- `duplicate -> near_duplicate` without explicit re-evaluation

Typical triggers:

- `unknown -> unique`: no duplicate found
- `unknown -> near_duplicate`: similarity threshold triggered
- `unknown -> duplicate`: exact duplicate detected
- `near_duplicate -> unique`: manual or improved algorithm reclassified item

## Reset Policy

When a stage is rerun intentionally:

- keep prior timestamps when useful for audit
- append a reason in `notes`
- move only the target stage back to `pending`

Examples:

- raw video deleted or corrupted:
  - set `download_status -> pending`
  - also set downstream stages back to `pending` because prerequisites broke
- ASR model change only:
  - keep `download_status = ok`
  - set `asr_status -> pending`
  - set `txt_sync_status -> pending`
  - keep `dedup_status = unknown` or reset it if transcript will materially change

## Downstream Reset Rules

When an upstream stage is invalidated, downstream stages cannot remain trusted.

| Upstream reset | Required downstream reset |
|---|---|
| download reset | reset ASR, txt sync, dedup |
| ASR reset | reset txt sync, dedup |
| txt sync reset | reset dedup |

These are not optional. They preserve graph consistency.

## Preconditions by Script

### `init_manifest`
- no pre-existing row required

### `sync_existing_txt_to_manifest`
- existing transcript txt file must exist
- row may be created or updated

### future download batch
- select rows where `download_status == pending`

### future ASR batch
- select rows where:
  - `download_status == ok`
  - `asr_status == pending`

### future txt sync batch
- select rows where:
  - `asr_status == ok`
  - `txt_sync_status == pending`

### future dedup batch
- select rows where:
  - `txt_sync_status == ok`
  - `dedup_status == unknown`

## Illegal State Examples

The repository layer should reject rows such as:

- `asr_status = ok` with empty `asr_provider`
- `txt_sync_status = ok` with empty `txt_path`
- `dedup_status = unique` while `txt_sync_status != ok`
- `download_status = ok` with empty `raw_video_path` for download-managed rows

## Phase 1 Completion Criteria

One row is considered foundation-complete when all of the following hold:

- `download_status == ok`
- `asr_status == ok`
- `asr_quality_grade in {A, B, C, D}`
- `txt_sync_status == ok`
- `dedup_status != unknown`

This does not mean “analysis-ready forever”. It only means the row passed the
Phase 1 foundation chain.
