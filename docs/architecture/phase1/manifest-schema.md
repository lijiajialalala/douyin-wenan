# Manifest Schema

## Purpose

`douyin_manifest.csv` is the runtime ledger for the corpus system. It tracks the
lifecycle of every work item from source link to standardized transcript asset.

Phase 1 keeps the schema intentionally narrow. It only contains the fields
needed for:

- identity
- source metadata
- download state
- ASR state and quality
- txt landing state
- dedup state

## Phase 1 Design Rules

1. The manifest is the only runtime ledger.
2. Every row represents exactly one Douyin work item.
3. Every script reads manifest rows, performs one bounded job, then writes
   changes back to the same row.
4. Derived files such as transcript txt files and dedup reports do not own
   workflow state.
5. The live manifest file is mutable runtime data and is not committed to Git.

## Field Groups

### Identity

- `work_id`
- `author`
- `platform`

### Source Metadata

- `video_link`
- `account_link`
- `title`
- `publish_time`
- `duration_text`
- `duration_seconds`
- `likes`
- `comments`
- `favorites`
- `shares`
- `followers`

### File Paths

- `raw_video_path`
- `raw_audio_path`
- `txt_path`

### Download State

- `download_status`
- `download_time`

### ASR State

- `asr_provider`
- `asr_model`
- `asr_time`
- `asr_status`
- `asr_char_count`
- `asr_chars_per_minute`
- `asr_quality_grade`
- `asr_quality_flags`
- `manual_reviewed`

### TXT Sync State

- `txt_sync_status`

### Dedup State

- `dedup_status`
- `dedup_group_id`

### Generic

- `notes`

## Column Specification

The table below defines the intended semantics for each Phase 1 field.

| Column | Required | Type | Meaning | Example | Phase 1 Notes |
|---|---|---:|---|---|---|
| `work_id` | yes | string | Stable unique ID for one work item | `7630818390835252514` | Prefer Douyin video ID |
| `author` | yes | string | Author display name used in corpus | `一代书生` | Must match transcript author dir naming |
| `platform` | yes | string | Source platform | `douyin` | Fixed enum in Phase 1 |
| `video_link` | yes | string | Canonical video URL | `https://www.douyin.com/video/...` | Primary external source pointer |
| `account_link` | no | string | Canonical author account URL | `https://www.douyin.com/user/...` | Useful for expansion and audits |
| `title` | yes | string | Work title or caption snapshot | `如果没有秦始皇...` | Stored as observed source metadata |
| `publish_time` | no | string | Publish time snapshot | `2026-04-20 20:32` | Keep as text in Phase 1 |
| `duration_text` | no | string | Original duration display | `07:32` | Raw display value |
| `duration_seconds` | no | integer | Parsed duration | `452` | Derived from `duration_text` when possible |
| `likes` | no | integer | Like count snapshot | `8376` | Source snapshot, not live-updated metrics |
| `comments` | no | integer | Comment count snapshot | `271` | Source snapshot |
| `favorites` | no | integer | Favorite count snapshot | `1619` | Source snapshot |
| `shares` | no | integer | Share count snapshot | `952` | Source snapshot |
| `followers` | no | integer | Author follower count snapshot | `3585000` | Author-level context at capture time |
| `raw_video_path` | no | string | Absolute path to downloaded video | `D:/.../raw_videos/...mp4` | Empty before download |
| `raw_audio_path` | no | string | Absolute path to extracted audio | `D:/.../raw_audio/...wav` | Optional retention |
| `txt_path` | no | string | Absolute path to standard transcript txt | `D:/.../整理版/...txt` | Empty before landing or sync |
| `download_status` | yes | enum | Download stage status | `pending` | `pending/ok/failed` |
| `download_time` | no | string | Timestamp of last successful download attempt | `2026-05-01T11:00:00+08:00` | ISO-ish text acceptable in Phase 1 |
| `asr_provider` | no | string | Provider used for ASR | `siliconflow` | Empty before ASR |
| `asr_model` | no | string | Exact ASR model used | `FunAudioLLM/SenseVoiceSmall` | Required for reproducibility |
| `asr_time` | no | string | Timestamp of last ASR run | `2026-05-01T11:05:00+08:00` | Used for audit and rerun logic |
| `asr_status` | yes | enum | ASR stage status | `pending` | `pending/ok/failed` |
| `asr_char_count` | no | integer | Character count of ASR transcript | `2876` | Computed from normalized transcript |
| `asr_chars_per_minute` | no | number | Character density over duration | `382.18` | Used for coarse quality screening |
| `asr_quality_grade` | no | enum | Human-usable quality grade | `B` | `A/B/C/D`, filled only after ASR |
| `asr_quality_flags` | no | string | Machine flags for anomalies | `low_density` | Pipe or comma-separated list later |
| `manual_reviewed` | yes | enum | Whether transcript got human review | `no` | `yes/no`, default `no` |
| `txt_sync_status` | yes | enum | Transcript landing status | `pending` | `pending/ok/failed` |
| `dedup_status` | yes | enum | Duplicate classification | `unknown` | `unknown/unique/near_duplicate/duplicate` |
| `dedup_group_id` | no | string | Group ID for near-duplicate cluster | `dup-20260501-0001` | Empty when not grouped |
| `notes` | no | string | Freeform operator notes | `asr rerun due to noisy audio` | Do not use as hidden machine state |

## Required Invariants

These invariants must hold once the repository layer exists.

### Identity invariants

- `work_id` must be unique within the manifest.
- `video_link` must not be empty.
- `platform` must be `douyin` in Phase 1.

### Stage invariants

- `asr_status == ok` requires `download_status == ok`
- `txt_sync_status == ok` requires `asr_status == ok`
- `dedup_status != unknown` requires a non-empty `txt_path`

### Quality invariants

- `asr_quality_grade` may only be filled when `asr_status == ok`
- `asr_chars_per_minute` may only be filled when both transcript text and
  `duration_seconds` are available

### Path invariants

- `raw_video_path` must be absolute when present
- `raw_audio_path` must be absolute when present
- `txt_path` must be absolute when present

## Creation Rules

### New row created from source metadata

When a row is first created, the minimum expected values are:

- identity fields filled
- source metadata filled as available
- `download_status = pending`
- `asr_status = pending`
- `txt_sync_status = pending`
- `dedup_status = unknown`
- `manual_reviewed = no`

### Row created from existing corpus txt

When bootstrapping from legacy transcript files:

- `txt_path` is filled immediately
- `txt_sync_status = ok`
- `asr_status` is inferred only if transcript provenance is clear
- `download_status` may remain `pending` or `unknown`-equivalent by policy;
  in Phase 1 we will normalize to `pending` unless raw asset presence is proven

## Mutability Rules

### Mutable in normal operation

- stage statuses
- stage timestamps
- file paths
- ASR metadata
- dedup fields
- notes

### Mutable only on explicit re-ingestion / metadata refresh

- title
- likes / comments / favorites / shares
- followers
- duration fields
- publish time

### Effectively immutable

- `work_id`
- `platform`
- original author identity after initial normalization

## Example Row

```csv
work_id,author,platform,video_link,account_link,title,publish_time,duration_text,duration_seconds,likes,comments,favorites,shares,followers,raw_video_path,raw_audio_path,txt_path,download_status,download_time,asr_provider,asr_model,asr_time,asr_status,asr_char_count,asr_chars_per_minute,asr_quality_grade,asr_quality_flags,manual_reviewed,txt_sync_status,dedup_status,dedup_group_id,notes
7630818390835252514,一代书生,douyin,https://www.douyin.com/video/7630818390835252514,https://www.douyin.com/user/...,如果没有秦始皇，今天的我们，还会是同一个“中国”吗？答案就藏在他被误解了两千年的三个操作里,2026-04-20 20:32,07:32,452,8376,271,1619,952,3585000,D:/.../raw_videos/一代书生/7630818390835252514.mp4,,D:/.../整理版/02_一代书生_如果没有秦始皇 今天的我们 还会是同一个 中国 吗 答案_8321.txt,ok,2026-05-01T11:00:00+08:00,siliconflow,FunAudioLLM/SenseVoiceSmall,2026-05-01T11:05:00+08:00,ok,2876,382.18,B,,no,ok,unknown,,
```

## Storage Rule

The live manifest file is ignored by Git:

`data/manifest/douyin_manifest.csv`

The repository stores only:

- schema definition
- header example
- fixtures for tests

## Implementation Consequences

This document implies the first implementation responsibilities:

- `manifest/schema.py` validates column presence, enum values, and row
  invariants
- `manifest/repository.py` performs safe read / write / update operations
- `scripts/init_manifest.py` creates a header-only runtime manifest
- `scripts/sync_existing_txt_to_manifest.py` backfills rows from legacy txt
  corpus files
