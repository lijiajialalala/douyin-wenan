# Script Contracts

## Purpose

This document locks the execution contract for Phase 1 scripts. The system must
behave like a data system, not a pile of sequential scripts.

## Global Contract

Every workflow script must satisfy:

`read manifest -> perform one bounded job -> write manifest`

## What Scripts May Read

### Always allowed
- manifest rows
- referenced standard txt files
- referenced local config
- schema definitions

### Allowed only when needed by the script's purpose
- raw video asset
- raw audio asset

## What Scripts May Write

### Always allowed
- manifest row updates
- standard-path files that belong to the script's domain

### Not allowed
- ad hoc status CSVs
- hidden sidecar files that become workflow truth
- randomly named logs as state records

## Phase 1 Script Catalog

### `init_manifest.py`

Purpose:
- create an empty runtime manifest file with the correct header

Reads:
- manifest schema

Writes:
- `data/manifest/douyin_manifest.csv`

Must not:
- infer business state
- scan corpus files

### `sync_existing_txt_to_manifest.py`

Purpose:
- backfill or refresh manifest rows from existing standardized transcript txt
  files

Reads:
- transcript txt files from configured corpus root
- manifest file if it already exists

Writes:
- manifest rows only

Must not:
- create parallel report CSVs as workflow state
- silently mutate unrelated fields

### `ingest_video_links.py`

Purpose:
- create or update manifest rows from explicit source-link inputs for new work
  items

Reads:
- manifest file if it already exists
- optional CSV/TSV input file

Writes:
- manifest rows only

Must:
- require explicit `author`, `video_link`, and `title`
- derive `work_id` deterministically
- leave operational statuses under manifest control

Must not:
- invent hidden placeholder metadata
- create parallel staging ledgers outside manifest

## Idempotency Requirement

Running the same script twice with the same input should not create duplicate
rows or contradictory state.

Examples:

- `init_manifest.py` should preserve the existing header if already initialized
- `sync_existing_txt_to_manifest.py` should upsert by stable key rather than
  append duplicate rows

## Error Handling Rule

When a script fails on one row:

- keep processing policy explicit
- write failure state to manifest where possible
- include enough reason text in `notes` for a human to diagnose

Silent failure is not acceptable.

## Future Rule

Any new script added later must first document:

1. what rows it selects
2. what fields it expects
3. what fields it mutates
4. what files it creates
5. what downstream states it invalidates
