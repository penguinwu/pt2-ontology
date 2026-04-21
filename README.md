# PT2 Domain Ontology

A structured, machine-readable domain ontology for PyTorch 2 (torch.compile) — capturing entities (components, symptoms, configs, workarounds, experts) and the relationships between them. Mined from 6,000+ GitHub issues, internal sources, and PyTorch source.

## Goal

Build an ontology that enables agents and humans to:
- **Triage issues** — symptom → failure mode → root cause → fix
- **Audit documentation** — surface stale, missing, or contradicted content (current Beaver use case)
- **Route diagnostics** — which tools to run for which user journey
- **Recommend resolutions** — prioritized fixes with type (compiler fix / workaround / adaptation)
- **Match experts** — given a topic, who can review?
- **Detect gaps** — concepts with weak coverage or missing relationships

## Stats (v0.17.1)

**Entities — 405 total across 15 types:**

| Type | Count | File |
|------|------:|------|
| Causes | 118 | `entities/causes.json` |
| Symptoms | 62 | `entities/symptoms.json` |
| Components | 43 | `entities/components.json` |
| Configs | 40 | `entities/configs.json` |
| User fix shortcuts (workarounds) | 33 | `entities/user_fix_shortcuts.json` |
| Experts | 27 | `entities/experts.json` |
| Failure modes | 17 | `entities/failure_modes.json` |
| Resolutions (categories) | 14 | `entities/resolutions.json` |
| Platforms | 10 | `entities/platforms.json` |
| Ops | 9 | `entities/ops.json` |
| User journeys | 9 | `entities/user_journeys.json` |
| Ecosystem | 8 | `entities/ecosystem.json` |
| Backends | 6 | `entities/backends.json` |
| Optimizations | 5 | `entities/optimizations.json` |
| Deprecated components | 4 | `entities/deprecated_components.json` |

**Relationships — 1,161 total across 13 layers:**

| File | Count | What |
|------|------:|------|
| `evidence_edges.json` | 294 | Multi-type relationships with evidence counts |
| `resolved_by_pr.json` | 228 | Symptom/failure → fixing PR |
| `diagnostic.json` | 152 | Diagnostic relationships (causes, is_symptom_of, diagnosed_by) |
| `weighted_evidence.json` | 107 | Edges weighted by evidence frequency |
| `resolution_map.json` | 100 | Symptom → fix-type mapping |
| `triage_paths.json` | 62 | One diagnostic path per symptom |
| `structural.json` | 51 | is_component_of, depends_on |
| `causal_chains.json` | 50 | High-level cause/effect chains |
| `journey.json` | 42 | routes_to, enters_via, involves |
| `other.json` | 35 | affects, triggers, related_to |
| `resolution.json` | 30 | fixed_by, resolved_by |
| `component_playbooks.json` | 6 | Per-component diagnostic guides |
| `triage_tree.json` | 4 | Top-level triage entry points |

**Other state:**
- Visibility classification layer in place (`oss` / `internal` / `confidential`) — see `ontology/VISIBILITY.md`
- Due-diligence scrubbing complete — unixnames replaced, experts tagged `internal`
- Triage tree entry points map to topics for the doc audit rubric (see `docs/beaver-integration.md`)

## Data Sources

| Source | What it provides | Status |
|--------|-----------------|--------|
| PyTorch source code (`torch/_dynamo/config.py`, etc.) | Configs, components, ops | Extracted |
| GitHub Issues (`oncall: pt2`, 6,167 issues, 4,677 comments) | Causes, symptoms, resolutions, evidence counts | Extracted (Phase 1+2 complete) |
| PyTorch docs (pytorch.org) | Component descriptions, API surface | Extracted |
| PT2 program working group (Workplace) | Vocabulary, strategy, roadmap concepts | Extracted |
| torch.compile doc audit project | User journeys, diagnostic tooling reference | Integrated |
| PT2 STO Structure + Issue Health Design Doc | STO owners, GitHub label mappings on 43 components | Integrated |
| PyTorch Conference (Paris, Apr 2026) | New features, best practices | Planned (Priority 2) |
| Internal PT2 Q&A group / chats / oncall logs | User pain points, expert responses | Planned (Priority 2) |

## Project Structure

```
pt2-ontology/
├── README.md                     ← this file
├── CLAUDE.md                     ← agent conventions, roles, privacy rules
├── ROADMAP.md                    ← living planned next steps (compass, not contract)
├── METHODOLOGY.md                ← extraction pipeline rebuild guide
├── ontology/
│   ├── schema.json               ← entity + relationship type definitions
│   ├── glossary.md               ← human-readable definitions
│   ├── VISIBILITY.md             ← classification rules (oss/internal/confidential)
│   ├── entities/                 ← 15 JSON files (one per entity type)
│   ├── relationships/            ← 13 JSON files (one per relationship layer/view)
│   └── views/                    ← auto-generated markdown views
├── docs/
│   └── beaver-integration.md     ← rubric interface design for doc audit
├── tools/
│   ├── generate_rubric.py        ← derive audit rubric from ontology
│   └── export_filter.py          ← strip non-oss content for public export
├── validation/
│   ├── freshness.py              ← entity freshness checks
│   ├── source_validator.py       ← verify configs exist in PyTorch source
│   └── drift_check.py            ← detect ontology drift over time
├── extraction/                   ← extraction scripts and intermediate data
├── data/                         ← raw + processed data (large files gitignored)
├── research/                     ← background notes on extraction approaches
└── skills/                       ← reusable agent skills
```

`ontology/skeleton.json` (the older monolithic file) is gitignored — modular files in `entities/` and `relationships/` are the source of truth.

## Key Design Decisions

### Entity lifecycle (current → deprecated → removed)

Entities carry a `lifecycle` field with three states: `current`, `deprecated`, `removed`. Status transitions carry a `since_version` and provenance (PR / commit / RFC / release notes). Deprecated entities are linked to their successor via the `replaced_by` relationship (optional — some deprecations have no successor). **Never delete entities** — historical entries are needed for auditing older docs.

### Visibility classification (oss / internal / confidential)

Every entity and edge has a `visibility` field. The `tools/export_filter.py --level oss` script strips non-oss content for public sharing. See `ontology/VISIBILITY.md` for full rules.

### Entity roles in workflows

Entities play different roles depending on the workflow phase:
- **Diagnostic** — gives information (TORCH_LOGS, minifier, tlparse)
- **Action** — changes behavior (config flags, code rewrites, upstream fixes)
- **Both** — context-dependent (`fullgraph=True` can diagnose or enforce)

### Fix types

Resolutions are classified by who changes what and why:
- `compiler_fix` — change compiler config/flag
- `upstream_fix` — PR to fix bug in PyTorch
- `user_workaround` — temporary user code change (bug should be fixed upstream)
- `user_adaptation` — permanent user code change (fundamental system limitation)

### Cause tree (funnel structure)

Causes have depth — failure modes fan out to cause categories, which fan out to specific sub-causes. Modeled via `is_subcause_of` relationships. Example: `graph_break → unsupported_op → [hundreds of specific ops]`.

### Two-tier journey model

From the torch.compile doc audit project:
- **Tier 1 (symptom):** J1-J3 — where users land, defined by what they *see*
- **Tier 2 (root cause):** J4-J8 — where problems get solved, requires compiler knowledge
- **Deployment:** J9 — entered intentionally

## Roles

| Who | Role |
|-----|------|
| **Peng Wu** | Project owner — strategic direction, priorities, external coordination |
| **Prof** | Tech lead — ontology architecture, entity/relationship design, quality gates |
| **Beaver** | First user — consumes ontology as rubric for PT2 doc audit; feeds gap/staleness findings back |
| **Rocky / Sentinel** | Future user — may consume ontology for automated issue triage |

## Roadmap

See `ROADMAP.md` for living priorities. Current focus: Beaver doc-audit integration (Priority 1). Next data sources (Priority 2): PyTorch Conference materials, internal PT2 Q&A and chat groups, oncall logs. Phase 2 scope expansion: torch.export. Phase 3: Helion.
