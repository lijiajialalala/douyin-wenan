# Transcript Output

The standardized corpus file stays as `txt`, not `md`.

Reason:

1. corpus files are data assets, not reports
2. plain text is easier for parsing and dedup
3. markdown formatting would add noise into the stored transcript body

## Runtime Separation

There are now two roots with different responsibilities:

1. `legacy_input_root`
   - old transcript corpus
   - read-only input
   - never used as output target

2. `runtime_root`
   - all new pipeline outputs
   - manifest
   - raw media
   - ASR snapshots
   - canonical transcript corpus

Legacy txt files are tracked in manifest through `legacy_txt_path`.

Canonical runtime transcript files are tracked in manifest through `txt_path`.

These two paths must never be conflated.

## Output Location

Canonical transcript files live under:

`runtime_root/corpus/{author}/transcripts/`

Example:

- `D:/视频创作/douyin-wenan-data/corpus/无名书生/transcripts/7633089780427091572_茶花女的破产清算.txt`

## Filename Rule

Runtime transcript files use:

- `{work_id}_{title-segment}.txt`

Reason:

1. `work_id` keeps manifest-to-file tracing direct
2. the title segment keeps the file readable for human review
3. the parent directory already scopes by author, so author is not repeated in the filename

## Internal Structure

The transcript txt keeps a stable, parse-friendly structure:

1. metadata header
2. `正文总结` placeholders
3. `正文文案：` body

Template source:

- `schemas/txt_template.md`

## Body Formatting

The body text is rendered from cleaned ASR text:

1. remove emoji and noise markers
2. apply a small high-confidence typo replacement table
3. keep plain text content only
4. wrap long continuous text into readable sentence-based paragraphs

This keeps the file usable both for human review and later script parsing.
