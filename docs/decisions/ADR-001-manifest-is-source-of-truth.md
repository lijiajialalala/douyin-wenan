# ADR-001: Manifest Is the Source of Truth

## Status

Accepted

## Context

The legacy workflow accumulated state in multiple places:

- transcript txt files
- per-step CSV logs
- ad hoc reports
- script-local status logic

That model does not scale. It creates multiple competing truths and makes
restart, audit, and validation hard.

## Decision

Use one runtime ledger:

`data/manifest/douyin_manifest.csv`

All workflow scripts must:

1. read rows from manifest
2. perform exactly one bounded job
3. write state changes back to manifest

## Consequences

### Positive

- status becomes queryable and restartable
- failures can be retried cleanly
- every work item is traceable by `work_id`

### Negative

- scripts need stricter discipline
- derived CSVs can no longer own workflow state
- txt files are no longer allowed to be the hidden source of truth

