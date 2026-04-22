# Inputs — `extractors/graph_break_site/`

## Pinned source

The graph-break catalog is auto-generated from PyTorch source on every
PyTorch release / nightly. Each entry corresponds to an
`unimplemented(gb_type=..., explanation=...)` call site in
`torch/_dynamo/`.

| Variable          | Value                                                      |
|-------------------|------------------------------------------------------------|
| `CATALOG_INDEX`   | https://meta-pytorch.org/compile-graph-break-site/         |
| `CATALOG_DETAIL`  | https://meta-pytorch.org/compile-graph-break-site/gb/gbNNNN.html |

Because the page is mutable (regenerated per Dynamo source change), the
extractor reads from a **pinned snapshot** under `snapshots/`. Snapshots
are filename-tagged with the SHA-256 prefix of their bytes, so the same
content always produces the same filename.

## Files read by each extractor

| Extractor          | Reads                                                  |
|--------------------|--------------------------------------------------------|
| `catalog_index.py` | `snapshots/index_<sha12>.html` (latest by default)    |

## Refreshing

To re-extract against a newer catalog snapshot:

```bash
# 1. Start the web-proxy in a separate terminal (see ~/.claude/skills/web-proxy)
# 2. Snapshot the current index page:
make snapshot-graph-break-site
# 3. Re-run the extractor:
python -m extractors.graph_break_site.catalog_index
```

The output's `provenance.extracted_from` records the snapshot SHA, so
diffing two extractor outputs reveals exactly which catalog entries
were added/removed/renamed between snapshots.

## Why snapshot, not live-fetch?

`REPRODUCIBILITY.md` requires byte-identical reruns. A live HTTP fetch
violates that the moment the page changes upstream. The snapshot acts
as a frozen input — the extractor is purely a function of the snapshot
file. Refreshing the snapshot is an explicit action, not a side effect
of running the extractor.
