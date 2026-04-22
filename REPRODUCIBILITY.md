# Reproducibility — PT2 Ontology

The ontology JSON files in `ontology/entities/` and `ontology/relationships/` are
**build artifacts**. The source of truth is the extractors in `extractors/` plus
the pinned inputs they declare. Re-running the pipeline against the same pinned
inputs must produce a byte-identical ontology.

This document defines the contract that makes that true.

## 1. Source of truth

| Layer                            | Status                  |
|----------------------------------|-------------------------|
| `extractors/`                    | Source of truth (code)  |
| `extractors/*/INPUTS.md`         | Source of truth (pins)  |
| `extractors/*/snapshots/`        | Source of truth (frozen sources) |
| `ontology/entities/*.json`       | Build artifact          |
| `ontology/relationships/*.json`  | Build artifact          |
| Hand-curated overlays            | Source of truth (marked `manually_curated: true`) |

A reviewer who clones the repo at any commit can:
1. Run the extractor pipeline.
2. Diff the regenerated `ontology/` against the committed one.
3. See zero diff (within tolerance for hand-curated overlays).

## 2. Provenance per fact

Every extracted entity carries a `provenance` block:

```json
{
  "id": "dynamo_unsupported",
  "name": "torch._dynamo.exc.Unsupported",
  "...": "...",
  "provenance": {
    "extracted_by": "pytorch_source.exc_classes@1.0.0",
    "extracted_from": "pytorch@d7d04823795:torch/_dynamo/exc.py:42",
    "extracted_at": "2026-04-22T03:00:00+00:00"
  }
}
```

- `extracted_by`: extractor module + semantic version
- `extracted_from`: stable source reference (commit SHA + path + line, or URL + snapshot SHA-256)
- `extracted_at`: ISO 8601 UTC, second precision

## 3. Pinning inputs

Every extractor domain has an `INPUTS.md` file. It declares:

- Which sources it reads (paths, URLs, GChat space IDs, etc.)
- The exact pinned reference (commit SHA, snapshot filename, fetched_at timestamp)
- How to update the pin (e.g., "to refresh: bump SHA in `_PYTORCH_SHA` and rerun")

Without a pinned input, an extractor cannot be considered reproducible — different
runs would silently drift as upstream sources change.

## 4. Snapshotting non-deterministic sources

For sources that mutate over time (web pages, social/chat threads, GitHub issue
bodies that can be edited):

- The extractor fetches the source once and writes a snapshot under
  `extractors/<domain>/snapshots/<label>_<sha_prefix>.<ext>`.
- All subsequent extractor runs read the snapshot, not the live source.
- Refreshing the snapshot is a deliberate, separately-committed step.

## 5. Hand-curation overlay

Some fields will always be hand-curated:
- Beaver's audit findings (`audit_status`, `audit_notes`)
- Peng's classifications (e.g., MegaCache → `optimization`)
- Subjective triage hints

These are preserved across re-extractions via the `manually_curated: true` marker
on the field or the entity. Extractor merge logic must:

1. Always overwrite extractor-owned fields (those marked in the extractor's schema).
2. Never overwrite fields marked `manually_curated`.
3. Surface conflicts (extractor says X, hand-curation says Y) as a diff for human review.

## 6. Canonical JSON serialization

All ontology JSON is written via `extractors/common/io.py:write_canonical_json`:
- 2-space indent
- Sorted keys
- UTF-8, no ASCII escaping
- Trailing newline

This guarantees byte-identical output across runs and platforms.

## 7. Re-running the pipeline

```bash
# Run all extractors, write to ontology/
make extract

# Dry-run; non-zero exit if outputs would change vs. the committed JSON
make extract-verify
```

CI runs `make extract-verify` on every PR — any drift between the extractors and
the committed ontology is caught at review time.

## 8. What's NOT yet reproducible

Honest accounting (as of v0.18 / 2026-04-22):
- The original Phase 1/Phase 2 issue extraction (`extraction/extract_*.py`) ran
  against a GitHub snapshot that was not pinned. Future work: snapshot the
  `j*_issues.jsonl` files and bump them deliberately.
- Hand-curated entries pre-dating the `manually_curated` marker are not yet
  flagged. Migration: a one-time pass to mark entries by audit.

The framework lands first; back-filling reproducibility for legacy data is
incremental.
