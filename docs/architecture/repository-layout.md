# Repository Layout

## Purpose

This document defines what each top-level directory is allowed to contain in
Phase 1. The goal is to keep the repository from turning into a script dump.

Runtime data is explicitly outside the repository and belongs under the
configured `runtime_root`.

## Top-Level Structure

```text
docs/
schemas/
configs/
src/
scripts/
data/
tests/
```

## Directory Responsibilities

### `docs/`

Human-facing design and decision records.

Allowed:
- architecture notes
- state machine definitions
- ADRs
- runbooks

Not allowed:
- runtime data
- generated reports that will constantly churn
- experimental scratch notes without decision value

### `schemas/`

Shared static schema artifacts.

Allowed:
- manifest schema definition
- transcript template
- future label schema definitions

Not allowed:
- Python logic
- runtime CSVs

### `configs/`

Example config and local config contract.

Allowed:
- `local.example.yaml`
- future provider or path config examples

Not allowed:
- secrets
- committed machine-specific local config

### `src/`

Library code only. Real logic belongs here.

Allowed:
- repository layer
- manifest validation
- future pipeline modules

Not allowed:
- one-off shell replacements
- ad hoc data dumps
- notebook-style scratch scripts

### `scripts/`

Thin CLI entrypoints that call library code from `src/`.

Allowed:
- argument parsing
- calling repository functions
- invoking one bounded operation

Not allowed:
- large embedded business logic
- duplicated logic that should live in `src/`

### `data/`

Repository-safe small data only.

Allowed:
- fixtures
- examples
- header-only templates

Not allowed in Git-tracked form:
- live manifest
- raw media
- snapshots
- large intermediate outputs

### `tests/`

Validation of repository logic and schema assumptions.

Allowed:
- schema tests
- state transition tests
- fixture-driven repository tests

Not allowed:
- integration against private live data by default

## Phase 1 Implementation Boundary

Even though the repository includes placeholder packages for:

- `ingest`
- `transcribe`
- `normalize`
- `dedup`
- `pipeline`

Phase 1 implementation is intentionally limited to:

- `manifest/schema.py`
- `manifest/repository.py`
- `manifest/transitions.py`
- `scripts/init_manifest.py`
- `scripts/sync_existing_txt_to_manifest.py`

Everything else remains skeletal until the foundation is stable.

## Ownership Rule

If a new file does not clearly fit one of the directory contracts above, do not
create it yet. Resolve the contract question first, then add the file.
