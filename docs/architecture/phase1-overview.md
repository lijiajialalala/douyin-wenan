# Phase 1 Overview

## Goal

Phase 1 only establishes the corpus foundation. It does not include content
typing, style labels, author analysis upgrades, or skills evidence grading.

The only supported chain in this phase is:

`manifest -> state-driven batch -> ASR quality -> dedup -> transcript landing`

## Non-Goals

- no full analysis pipeline rewrite
- no content type classifier
- no style rule validation set
- no skills distillation rewrite
- no multimodal cover / frame analysis

## Core Principle

Every script must follow one contract:

`read manifest -> do one job -> write manifest`

If a status exists only in `txt` files or only in derived CSV reports, that is a
system defect and must be removed over time.

## Document Authority

To avoid design drift, each document owns one kind of truth:

- [manifest-schema.md](C:/projects/douyin-wenan/docs/architecture/manifest-schema.md):
  field truth
- [state-machine.md](C:/projects/douyin-wenan/docs/architecture/state-machine.md):
  state truth
- [script-contracts.md](C:/projects/douyin-wenan/docs/architecture/script-contracts.md):
  execution truth

## Phase 1 Output

- stable repository layout
- manifest schema and state machine
- manifest repository abstraction
- initialization path for new manifest creation
- backfill path from existing transcript corpus
