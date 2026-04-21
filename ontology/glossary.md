# PT2 Ontology — Glossary

Human-readable definitions for entity types, relationship types, and structural conventions in the ontology.

## Entity Types (15)

### Component
A software component or subsystem in the PT2 compilation stack. Components have a hierarchical structure (e.g., guards are part of dynamo, which is part of torch.compile). 43 entries.

### Deprecated Component
A component that has been removed or replaced. Kept separate from active components to preserve historical references in older docs and issues. 4 entries.

### Failure Mode
A category of things that can go wrong when using torch.compile. Abstract categories (e.g., "graph break"), not specific instances. 17 entries.

### Symptom
An observable signal that something is wrong — what the user *sees*. Often error messages, warnings, or performance anomalies. A single failure mode can have multiple symptoms. 62 entries.

### Cause
A root cause that triggers a failure mode. Causes are structural — they describe *why* something goes wrong (e.g., "data-dependent control flow"). Forms a funnel structure via `is_subcause_of`. 118 entries.

### Resolution
A category of fix or workaround (e.g., `config_change`, `upstream_fix`, `code_rewrite`). 14 entries.

### User Fix Shortcut (Workaround)
A specific, named user-facing fix — concrete advice users can apply (e.g., set a particular flag, replace one API call with another). Distinct from the abstract Resolution category. 33 entries.

### Config
A configuration flag or setting that affects compilation behavior. 40 entries.

### Op
A PyTorch operator or function. The atomic units of computation the compiler reasons about. 9 entries.

### Backend
A compilation backend torch.compile can target (default is inductor; others exist for debugging or specialized use). 6 entries.

### Ecosystem
An external project, benchmark, or framework that interacts with PT2 (e.g., HuggingFace, vLLM, TorchBench). 8 entries.

### Optimization
A specific optimization technique or pass within the compiler. 5 entries.

### User Journey
A user-facing problem scenario that defines a diagnostic and resolution workflow. 9 entries — map to the doc audit's user-facing topic structure.

### Platform
A hardware accelerator (NVIDIA GPU, AMD GPU, Intel XPU, TPU, ARM CPU, Apple MPS) or operating system that affects diagnosis and support level. 10 entries.

### Expert
An engineer with deep knowledge of a specific component or area, mapped to anonymized IDs (`engineer_XX`). Always tagged `visibility: internal`. 27 entries.

## Relationship Types

### Structural

| Relationship | Meaning |
|---|---|
| `is_component_of` | X is a sub-component of Y (e.g., dynamo `is_component_of` torch.compile) |
| `depends_on` | X depends on Y at runtime or compile time |

### Diagnostic

| Relationship | Meaning |
|---|---|
| `causes` | X (cause) leads to Y (failure_mode) |
| `is_symptom_of` | X (symptom) indicates Y (failure_mode) |
| `is_subcause_of` | X (specific cause) is a sub-cause of Y (cause category) — supports funnel/tree structure |
| `diagnosed_by` | X (failure_mode/journey) is diagnosed using Y (diagnostic tool/config) |
| `triggers` | X (event/condition) triggers Y (behavior) |
| `affects` | X (failure_mode) affects Y (component) |

### Resolution

| Relationship | Meaning |
|---|---|
| `fixed_by` | X (failure_mode) can be resolved by Y (resolution category) |
| `resolved_by` | X (failure_mode/journey) is resolved by Y (resolution); carries `fix_type` property |

### Journey

| Relationship | Meaning |
|---|---|
| `enters_via` | X (journey) is entered when user observes Y (symptom/failure_mode) |
| `routes_to` | X (journey) routes to Y (journey) when diagnostic reveals specific root cause |
| `involves` | X (journey) involves Y (component/config/op) as relevant context |

### Lifecycle

| Relationship | Meaning |
|---|---|
| `replaced_by` | X (deprecated/removed entity) is replaced by Y (current entity); carries `since_version` and provenance. Optional — some deprecations have no successor. |

### Platform

| Relationship | Meaning |
|---|---|
| `platform_specific` | X (cause/failure_mode) is specific to or primarily affects Y (platform) |

### Other

| Relationship | Meaning |
|---|---|
| `related_to` | General semantic association (use sparingly — prefer specific relationships) |

## Structural Conventions

### Entity lifecycle

Every entity may carry a `lifecycle` field:

```json
"lifecycle": {
  "status": "current | deprecated | removed",
  "since_version": "v2.4.0",
  "reason": "Replaced by X for Y",
  "provenance": {
    "type": "pr | commit | rfc | release_notes | issue | docs",
    "ref": "https://...",
    "id": "PR-12345"
  }
}
```

- Default: `status: current` — entries without an explicit lifecycle field are assumed current
- `since_version` required if `status != current`
- `provenance` strongly recommended for `deprecated` and `removed` — it powers doc-audit confidence (without provenance, downstream consumers can't cite *why* something is stale)
- For renamed/replaced entities, also create a `replaced_by` edge to the successor

This schema is intentionally minimal — we expect it to evolve as Beaver and other consumers surface concrete needs from real audit cases.

### Visibility

Every entity and edge carries `visibility: oss | internal | confidential`. See `VISIBILITY.md` for classification rules. Export filter (`tools/export_filter.py`) drops non-`oss` content for public sharing.

### Freshness

Entities also carry a separate `freshness` field (`base | living | historical | stale`) tracking how actively the entity is being updated, distinct from its lifecycle status. A `current` entity can still be `stale` (no recent updates).

### Provenance

Every entity carries `source` and `evidence_issues` (list of GitHub issue IDs supporting it). Edges carry `evidence_count`.

### IDs

- Entity IDs are `snake_case` (e.g., `duck_sizing_recompilation`)
- Component IDs are lowercase (e.g., `torchdynamo`, `torchinductor`)

## Notes on Ontology Design

- **Entities are types, not instances.** The ontology defines `graph_break` as a concept; individual issues that *are* graph breaks are instances that reference this concept.
- **Relationships are directional.** "X causes Y" is different from "Y causes X".
- **Aliases matter.** Users say "compile" not "torch.compile", "dynamo" not "TorchDynamo". The `aliases` field captures variations for entity resolution during extraction.
- **Severity is relative.** A "critical" failure (wrong output) is always worse than a "medium" one (graph break), but severity can be context-dependent.
