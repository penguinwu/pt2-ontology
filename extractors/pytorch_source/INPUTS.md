# Inputs — `extractors/pytorch_source/`

## Pinned source

Extractors in this directory walk the PyTorch source tree.

| Variable        | Value                                          |
|-----------------|------------------------------------------------|
| `PYTORCH_ROOT`  | `~/projects/pytorch`                           |
| `PYTORCH_HEAD`  | resolved at extraction time via `git rev-parse HEAD` |

The HEAD SHA is captured into the `extracted_from` provenance field of every
emitted entity, so any reader can pin the exact source state.

## Files read by each extractor

| Extractor                   | Reads                                       |
|-----------------------------|---------------------------------------------|
| `exc_classes.py`            | `torch/_dynamo/exc.py`                      |
| `config_docstrings.py`      | `torch/_dynamo/config.py`                   |
| `unsupported_calls.py`      | `torch/_dynamo/**/*.py` (greps Unsupported) |

## Refreshing

To re-extract against a newer PyTorch:

```bash
cd ~/projects/pytorch && git pull
cd ~/projects/pt2-ontology && make extract-pytorch-source
```

The provenance line on each emitted entity will show the new SHA. Diff the
output against the previous commit to see what changed in PyTorch (renames,
new classes, removed configs, etc.) — that diff is the real signal.

## When to bump `PYTORCH_ROOT`

If PyTorch source moves (e.g., Meta-internal `fbsource` mirror), update the
default in `extractors/pytorch_source/_root.py`. The fallback chain is
explicit there, not silently inferred.
