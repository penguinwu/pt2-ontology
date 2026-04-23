# LLM-Distillation Extractors

Distills unstructured text (chat threads, issue bodies, doc comments) into
ontology entities via LLM calls. Designed to satisfy the same reproducibility
contract as the source-mining extractors (see `REPRODUCIBILITY.md`).

## Why this is harder than source-mining

Source-mining is byte-deterministic: pinned source + AST walk = same answer
every time. LLM distillation isn't — even at `temperature=0`, model-provider
weight updates make raw LLM calls non-reproducible.

The fix: **cache the LLM response**. The cache IS the determinism mechanism.
On every rerun, we read responses from the on-disk cache instead of re-calling
the LLM. Cache miss = call LLM, write response, commit.

## Pipeline shape

```
  raw source
      │ (1) snapshot
      ▼
  snapshots/<source>_<sha12>.json     ← frozen, content-addressed
      │ (2) build prompt
      ▼
  prompts/extract_*.md                ← versioned in repo
      │ (3) compute cache key, check cache
      ▼
  cache/<key>.json                    ← if miss, call LLM, write+commit
      │ (4) parse + validate
      ▼
  schemas/*.json                      ← schema-constrained output
      │ (5) write to staging
      ▼
  ontology/distilled/<source>_<date>.json   ← unreviewed, distilled
      │ (6) human review (Beaver audit → Peng approval)
      ▼
  ontology/entities/*.json            ← reviewed, promoted
```

## Cache mechanics

For each LLM call:

```
key = sha256(input_snapshot_sha + prompt_sha + model + temperature + schema_sha)
```

- Cache miss → call LLM → write `cache/<key>.json` → commit
- Cache hit → read `cache/<key>.json` → no API call

**Auto-invalidation:** any change to input/prompt/model/temp/schema changes the
key, so reruns naturally re-extract. No manual "is this stale?" flag.

**Storage choice:** one JSON per call (option (a)). Inspectable with `cat`,
git-diffable in PRs, easy to delete one entry. We can migrate to SQLite if we
ever exceed ~10k cached calls; for v1 the file-per-call layout is fine.

## Layer separation (option (c) — hybrid)

- `ontology/distilled/<source>_<date>.json` — distilled, **not yet reviewed**.
  Carries provenance: `extracted_by: llm_distill@vN, prompt_sha, model,
  cache_key, manually_curated: false, source_type: llm_distilled`.
- `tools/promote_distilled.py` — manual promotion. Beaver audits the diff,
  Peng approves, the script merges entries into `ontology/entities/*.json`
  with the `source_type: llm_distilled` flag preserved.
- `ontology/entities/` — reviewed entities only. Anyone reading this directory
  can trust it has had human review.

## Promotion mechanism (option (a))

1. Pipeline writes to `ontology/distilled/`.
2. Beaver audits the new file (in his audit lane).
3. Peng final-approves the audit findings.
4. `tools/promote_distilled.py <source>_<date>.json` merges approved entries
   into `ontology/entities/`, preserving the `llm_distilled` flag and full
   provenance chain.
5. Audit log appended to `ontology/distilled/PROMOTIONS.log` (who promoted,
   when, what cache_key, what source_sha).

## How to add a new source

1. Add a snapshot of the input to `snapshots/<source>_<sha12>.json`.
2. Add an entry to `INPUTS.md` declaring source URL/path + snapshot SHA.
3. Pick (or write) a prompt template in `prompts/<intent>_v<N>.md` and a
   matching schema in `schemas/<intent>_v<N>.json`.
4. Add a subclass of `DistillExtractor` (in `distill.py`) that points at the
   snapshot, prompt, and schema.
5. Run `make extract-llm-distill` — first run populates the cache, subsequent
   runs are instant + reproducible.

## Status

**v0.0 skeleton.** No working LLM client yet. Stub files show the contract
and let us iterate on the design before wiring up real API calls.
