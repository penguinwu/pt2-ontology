# Visibility Classification Rules

Every entity and relationship in the ontology carries a `visibility` field that controls
what can be shared outside Meta's boundary.

## Levels

| Level | Meaning | Can publish externally? |
|-------|---------|------------------------|
| `oss` | Derived from open source data (GitHub, pytorch.org, public talks) | Yes |
| `internal` | Derived from internal-only sources, but not competitive/sensitive | No — Meta-only |
| `confidential` | Contains proprietary model names, perf data, or team intel | No — restricted access |

## Classification Rules

### Automatic `oss` (safe for open)
- Config/flag names that exist in open source PyTorch code
- Error messages and stack traces from public GitHub issues
- GitHub handles and issue/PR numbers
- PyTorch version numbers and release dates
- Diagnostic patterns derived from public documentation
- Error signatures (exception class names, warning text)
- Public PyTorch conference talk content

### Automatic `internal`
- Meta employee unixnames (e.g., `engineer_14`, `engineer_02`)
- References to internal Workplace groups or chat channels
- References to internal tools (e.g., Scuba datasets, internal dashboards)
- Workarounds discovered in internal Q&A but using only OSS flags
  (the workaround config itself is `oss`, but the context/attribution is `internal`)
- Oncall rotation information
- Internal team structure or org mappings

### Automatic `confidential`
- Model names not in public PyTorch (e.g., internal ads models, pre-release LLMs)
- Performance numbers tied to specific internal workloads
- Internal model architecture details
- Customer-specific workarounds that reveal business relationships
- Security vulnerabilities not yet disclosed

### Edge cases — classify manually
- PyTorch conference slides: usually `oss` (public event), but check for internal-only slides
- Q&A posts: the question pattern may be `oss`, but model names in it make it `internal`
- Chat messages: default to `internal`, promote to `oss` only if the content is generic

## Scrubbing Rules for Internal Ingestion

When mining internal sources (Workplace, chat, oncall), apply these transformations:

1. **Model name scrubbing**: Replace specific model names with generic categories
   - "Avocado model" → "internal ads model"
   - "Llama 4x" → "internal LLM"
   - Keep the symptom/workaround, strip the model identity

2. **Person attribution**: 
   - GitHub handles → keep as-is (`oss`)
   - Unixnames → store but tag `internal`
   - Never include person names in `oss`-visible entities

3. **Performance data**:
   - Relative comparisons are OK for `oss` ("2x slower", "50% regression")
   - Absolute numbers tied to specific models → `confidential`
   - Public benchmark results (TorchBench, HuggingFace) → `oss`

4. **Workaround extraction**:
   - The config flag/API call itself → `oss` (it's in open source code)
   - The specific model/workload context → `internal` or `confidential`
   - Create two entities: one `oss` workaround + one `internal` context note

## Export Pipeline

Before publishing any ontology artifact externally:

```
1. Load all entities and edges
2. Filter: keep only visibility == "oss"
3. For edges: drop any edge where either endpoint is non-oss
4. Validate: no dangling references in the filtered graph
5. Output: clean OSS-only ontology
```

The export filter is implemented in `tools/export_filter.py`.

## Review Process

When adding entities from internal sources:
1. Auto-classify using rules above
2. Flag any entity that mentions a model name or person for manual review
3. Reviewer checks: "If this entity appeared on pytorch.org, would it reveal anything proprietary?"
4. When in doubt, classify as `internal` — it's easy to promote to `oss`, hard to un-publish.
