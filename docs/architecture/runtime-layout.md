# Runtime Layout

## Purpose

This document defines the official runtime data layout outside the repository.

The code repository stores code, schemas, tests, and docs.
The runtime root stores operational data.

## Roots

### Legacy Input Root

Read-only external source:

`D:/视频创作/书籍/视频文案/对标作者文案`

Used for:

- backfill
- manual comparison
- legacy reference

Not used for:

- new transcript output
- raw media output
- manifest storage

### Runtime Root

Official operational root:

`D:/视频创作/douyin-wenan-data`

## Directory Structure

```text
runtime_root/
  manifest/
    douyin_manifest.csv

  ingest/
    source_links/
      *.csv

  assets/
    raw_videos/
      {author}/
        {work_id}.mp4
    raw_audio/
      {author}/
        {work_id}.mp3

  snapshots/
    asr_text/
      {author}/
        {work_id}.txt

  corpus/
    {author}/
      transcripts/
        {work_id}_{title-segment}.txt

  analysis/
    {author}/
      *.md
      *.csv

  logs/
```

## Field-to-Artifact Mapping

| Manifest Field | Meaning |
|---|---|
| `legacy_txt_path` | read-only path to legacy input txt |
| `raw_video_path` | runtime raw video asset |
| `raw_audio_path` | runtime extracted audio asset |
| `asr_text_path` | runtime cleaned ASR snapshot |
| `txt_path` | runtime canonical transcript txt |

## Rules

1. scripts may read `legacy_input_root`, but may not write to it
2. all new outputs must land under `runtime_root`
3. `txt_path` always refers to runtime corpus output, never legacy input
4. runtime artifacts use stable machine naming first, readable title second
