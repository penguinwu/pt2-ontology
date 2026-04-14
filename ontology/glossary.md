# PT2 Ontology — Glossary

Human-readable definitions for all entity types and relationship types in the ontology.

## Entity Types

### Component
A software component or subsystem in the PT2 compilation stack. Components have a hierarchical structure (e.g., guards are part of dynamo, which is part of torch.compile).

### Failure Mode
A category of things that can go wrong when using torch.compile. These are abstract categories (e.g., "graph break"), not specific instances (e.g., "graph break on line 42 of my_model.py").

### Symptom
An observable signal that something is wrong — what the user *sees*. Symptoms are often error messages, warnings, or performance anomalies. A single failure mode can have multiple symptoms.

### Cause
A root cause that triggers a failure mode. Causes are structural — they describe *why* something goes wrong (e.g., "data-dependent control flow"), not *what* goes wrong.

### Resolution
A type of fix or workaround. Resolutions are strategies, not specific patches. A resolution like "code_rewrite" encompasses many specific code changes.

### Config
A configuration flag or setting that affects compilation behavior. Configs are knobs users can turn to change compile behavior.

### Op
A PyTorch operator or function. Ops are the atomic units of computation that the compiler reasons about.

### Model
A user model or model family. Useful for tracking which models are affected by which issues.

### Backend
A compilation backend that torch.compile can target. The default is inductor; others exist for debugging or specialized use cases.

## Relationship Types

| Relationship | Meaning | Example |
|---|---|---|
| `is_component_of` | X is a sub-component of Y | dynamo `is_component_of` torch.compile |
| `depends_on` | X depends on Y at runtime or compile time | inductor `depends_on` triton |
| `causes` | X (cause) leads to Y (failure_mode) | unsupported_op `causes` graph_break |
| `is_symptom_of` | X (symptom) indicates Y (failure_mode) | Unsupported error `is_symptom_of` graph_break |
| `fixed_by` | X (failure_mode) can be resolved by Y (resolution) | graph_break `fixed_by` code_rewrite |
| `triggers` | X (event/condition) triggers Y (behavior) | guard_mismatch `triggers` recompilation |
| `affects` | X (failure_mode) affects Y (component) | crash `affects` inductor |
| `related_to` | General semantic association | — |

## Notes on Ontology Design

- **Entities are types, not instances.** The ontology defines "graph_break" as a concept; individual issues that *are* graph breaks are instances that reference this concept.
- **Relationships are directional.** "X causes Y" is different from "Y causes X".
- **Aliases matter.** Users say "compile" not "torch.compile", "dynamo" not "TorchDynamo". The alias field captures these variations for entity resolution during extraction.
- **Severity is relative.** A "critical" failure (wrong output) is always worse than a "medium" one (graph break), but severity can be context-dependent.
