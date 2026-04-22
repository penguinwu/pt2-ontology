# PT2 Ontology Extractors

Reproducible mining pipeline for the PT2 ontology. Every entity in `ontology/`
should be traceable to a checked-in extractor + a pinned source reference.

## Layout

```
extractors/
  common/                        # shared utilities (io, provenance, base class)
  pytorch_source/                # extractors that walk PyTorch source
    INPUTS.md                    # PIN: pytorch HEAD + paths
    exc_classes.py               # torch/_dynamo/exc.py → symptom entities
    config_docstrings.py         # torch/_dynamo/config.py docstrings → config rationale
    unsupported_calls.py         # raise Unsupported(...) → cause candidates
  graph_break_site/              # extractors that pull the meta-pytorch.org catalog
    INPUTS.md
    catalog_index.py             # 455-entry index → graph_break aliases
    snapshots/                   # frozen copies of fetched HTML for reproducibility
```

## Determinism contract

1. **Code the extractor, not the result.** The JSON in `ontology/entities/` is a
   build artifact. Re-running an extractor with the same pinned inputs must
   produce a byte-identical file.
2. **Pin inputs.** Every extractor's `INPUTS.md` declares its source with a
   stable ref (commit SHA, snapshot file, URL + `fetched_at`).
3. **Provenance per fact.** Every extracted entity carries a `provenance` block:
   `extracted_by` + `extracted_from` + `extracted_at`. Hand-curated entries are
   marked `manually_curated: true` and preserved across reruns.
4. **Snapshot non-deterministic sources.** Web pages, GChat threads, and GitHub
   issue bodies can mutate. Extractors snapshot to `snapshots/` at extraction time
   so reruns hit the snapshot, not the live source.

## Adding a new extractor

1. Pick a source domain (or create `extractors/<domain>/`).
2. Write/extend `INPUTS.md` declaring exactly which inputs the extractor reads.
3. Implement an `Extractor` subclass (see `common/base.py`):
   - Set `extractor_id`, `extractor_version`, `output_path`
   - Implement `source_ref()` and `extract()`
4. Run it: `python -m extractors.<domain>.<module>`.
5. Verify the diff against the previous output is what you expect — no spurious
   churn from non-deterministic ordering, timestamps, etc.
6. Commit the extractor + its output in the same change.

## Re-running everything

```bash
make extract           # run all extractors, write to ontology/
make extract-verify    # dry-run; non-zero exit if outputs would change
```

(Makefile lands with the first end-to-end extractor.)
