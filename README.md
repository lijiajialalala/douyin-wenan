# douyin-wenan

Douyin short-video copy corpus engine.

Current scope is intentionally narrow. Phase 1 only builds the foundation:

1. `manifest` as the single source of truth
2. state-driven batch execution
3. ASR quality tracking
4. dedup entry points
5. standard transcript landing from existing corpus files
6. transcript noise cleaning and canonical txt output

This repository does not store full raw media assets in Git. Runtime data stays
outside version control. Only schemas, code, docs, fixtures, and small examples
are kept in the repository.

The pipeline now separates:

1. `legacy_input_root` for old read-only corpus input
2. `runtime_root` for all new operational outputs

## Phase 1 Deliverables

- repository skeleton
- manifest schema
- manifest state machine
- manifest repository layer
- manifest initialization script
- sync script for existing transcript files

## Repository Layout

```text
docs/       architecture and ADRs
schemas/    shared schemas and templates
examples/   example serialized assets and plans
configs/    example local config only
src/        library code
scripts/    CLI entrypoints
data/       fixtures and small repo-safe data only
tests/      validation for schema and state transitions
```

## Phase 1 Quickstart

1. Review and copy the example config if you need a local override:

   `configs/local.example.yaml`

2. Run tests:

   ```powershell
   python -m unittest discover -s tests -v
   ```

3. Initialize the live manifest:

   ```powershell
   python scripts/init_manifest.py
   ```

4. Backfill rows from existing standardized txt files:

   ```powershell
   python scripts/sync_existing_txt_to_manifest.py --limit 5
   ```

   Or only one author:

   ```powershell
   python scripts/sync_existing_txt_to_manifest.py --author 无名书生 --limit 5
   ```

   This only imports metadata and `legacy_txt_path`. It does not write back
   into the old corpus.

5. Preview rows eligible for state-driven batches:

   ```powershell
   python scripts/run_download_batch.py --dry-run --limit 10
   python scripts/run_asr_batch.py --dry-run --limit 10
   python scripts/run_txt_sync_batch.py --dry-run --limit 10
   python scripts/run_dedup_batch.py --dry-run --limit 10
   ```

6. Ingest new source links into manifest:

   ```powershell
   python scripts/ingest_video_links.py --author 无名书生 --video-link https://www.douyin.com/video/7633089780427091572 --title 茶花女
   ```

   Or from a CSV file with `author,video_link,title` columns:

   ```powershell
   python scripts/ingest_video_links.py --input-file data/fixtures/sample_links.csv
   ```

7. Run the real download batch:

   ```powershell
   python scripts/run_download_batch.py --author 无名书生 --limit 1
   ```

8. Run the real ASR batch:

   ```powershell
   $env:SILICONFLOW_API_KEY="your-key"
   $env:OPENAI_API_KEY="your-key"
   python scripts/run_asr_batch.py --author 无名书生 --limit 1
   ```

   ASR now writes three artifacts under `runtime_root/snapshots/asr_text/<author>/`:

   - `{work_id}.raw.txt` raw provider transcript
   - `{work_id}.txt` final transcript used downstream
   - `{work_id}.correction.json` OpenAI correction audit or fallback record

   To enable OpenAI correction, add a local override:

   ```yaml
   correction:
     enabled: true
     provider: "openai"
     model: "gpt-4.1-mini"
     base_url: "https://api.openai.com"
     api_key_env: "OPENAI_API_KEY"
   ```

9. Run the real txt sync batch:

   ```powershell
   python scripts/run_txt_sync_batch.py --author 无名书生 --limit 1
   ```

10. Refresh existing processed rows after cleanup or template changes:

   ```powershell
   python scripts/run_asr_batch.py --author 无名书生 --limit 1 --reclean-existing
   python scripts/run_txt_sync_batch.py --author 无名书生 --limit 1 --rewrite-existing
   python scripts/run_dedup_batch.py --author 无名书生 --limit 1
   ```

The live manifest is written under `runtime_root/manifest/douyin_manifest.csv`.

Transcript output policy:

- corpus files stay `txt`
- new generated files use `{work_id}_{title-segment}.txt`
- old corpus is read-only input and is not reused as output
- details are documented in `docs/architecture/phase1/transcript-output.md`
- runtime directory layout is documented in `docs/architecture/phase1/runtime-layout.md`
