# PT2 Domain Ontology

A structured, machine-readable domain ontology for PyTorch 2 (torch.compile) — capturing concepts, failure modes, causes, relationships, and user journeys.

## Goal

Build an ontology that enables agents and humans to:
- **Triage issues** — symptom → failure mode → root cause → fix
- **Route diagnostics** — which tools to run for which journey
- **Recommend resolutions** — prioritized fixes with type (compiler fix / workaround / adaptation)
- **Match experts** — given a topic, who can review?
- **Detect gaps** — concepts with weak coverage or missing relationships

## Stats

- **v0.6.0** — 262 entities | 310 relationships | 12 entity types | 12 relationship types
  - Beaver cause tree merge: 89 leaf subcauses mined from 9,277 GitHub issues with evidence counts
- 9 user journeys (from torch.compile doc audit project)
- 39 active components + 4 deprecated
- 28 config flags, 9 ops, 21 causes, 17 failure modes

## Data Sources

| Source | What it provides | Status |
|--------|-----------------|--------|
| PT2 program working group (Workplace) | Vocabulary, strategy, roadmap concepts | Extracted (v0.3) |
| PyTorch source code (`torch/_dynamo/config.py`, etc.) | Config flags, ops, components | Extracted (v0.4, Beaver) |
| GitHub Issues (`oncall: pt2`) | Causes, symptoms, resolutions, issue counts per journey | In progress (Beaver) |
| torch.compile doc audit project | User journeys, diagnostic tooling reference | Integrated (v0.5) |
| Official PyTorch docs (pytorch.org) | Component descriptions, API surface | Extracted (v0.4, Beaver) |

## Project Structure

```
pt2-ontology/
├── README.md
├── ontology/
│   ├── skeleton.json          ← monolithic file (kept for compatibility)
│   ├── schema.json            ← entity types + relationship types
│   ├── glossary.md            ← human-readable definitions
│   ├── entities/
│   │   ├── components.json        (39 active)
│   │   ├── deprecated_components.json (4)
│   │   ├── failure_modes.json     (17)
│   │   ├── causes.json            (21, expanding with sub-cause tree)
│   │   ├── symptoms.json          (13)
│   │   ├── resolutions.json       (14)
│   │   ├── configs.json           (28)
│   │   ├── ops.json               (9)
│   │   ├── backends.json          (6)
│   │   ├── ecosystem.json         (8)
│   │   ├── optimizations.json     (5)
│   │   └── user_journeys.json     (9)
│   ├── relationships/
│   │   ├── structural.json        (is_component_of, depends_on)
│   │   ├── diagnostic.json        (causes, is_symptom_of, diagnosed_by)
│   │   ├── resolution.json        (fixed_by, resolved_by)
│   │   ├── journey.json           (routes_to, enters_via, involves)
│   │   └── other.json             (affects, triggers, related_to)
│   └── views/                     ← auto-generated markdown
│       ├── overview.md
│       ├── j1-first-compile.md
│       ├── j2-perf-diagnosis.md
│       ├── j3-correctness.md
│       ├── j4-graph-breaks.md
│       ├── j5-dynamic-shapes.md
│       ├── j6-compile-time.md
│       ├── j7-perf-optimization.md
│       ├── j8-custom-ops.md
│       └── j9-export.md
├── data/
│   └── sources.md
└── extraction/                    ← future: extraction pipeline
```

## Key Design Decisions

### Entity roles in workflows
Entities play different roles depending on the workflow phase:
- **Diagnostic** — gives information (TORCH_LOGS, minifier, tlparse)
- **Action** — changes behavior (config flags, code rewrites, upstream fixes)
- **Both** — context-dependent (fullgraph=True can diagnose or enforce)

### Fix types
Resolutions are classified by who changes what and why:
- `compiler_fix` — change compiler config/flag
- `upstream_fix` — PR to fix bug in PyTorch
- `user_workaround` — temporary user code change (bug should be fixed upstream)
- `user_adaptation` — permanent user code change (fundamental system limitation)

### Cause tree (funnel structure)
Causes have depth — a failure mode fans out to cause categories, which fan out to specific sub-causes. Modeled via `is_subcause_of` relationships. Example: `graph_break → unsupported_op → [hundreds of specific ops]`.

### Two-tier journey model
From the torch.compile doc audit project:
- **Tier 1 (symptom):** J1-J3 — where users land, defined by what they *see*
- **Tier 2 (root cause):** J4-J8 — where problems get solved, requires compiler knowledge
- **Deployment:** J9 — entered intentionally

## Phases

### Phase 1: Skeleton ✅
- [x] Define entity types and relationship types
- [x] Draft seed ontology with known PT2 concepts
- [x] Review with Peng (3 rounds)
- [x] Merge Beaver's source code extraction (v0.4)
- [x] Add user journeys and diagnostic relationships (v0.5)

### Phase 2: Expansion (current)
- [x] Delegate cause tree and resolution mapping to Beaver
- [ ] Merge Beaver's is_subcause_of and resolved_by data
- [ ] Populate expert mapping (person → component)
- [ ] Restructure into modular file format ✅

### Phase 3: Validation
- [ ] Test triage workflow: given symptom, traverse to resolution
- [ ] Manual accuracy check on sample issues
- [ ] Agent integration test: can an agent navigate the ontology to answer user questions?

### Phase 4: Automation
- [ ] Scheduled refresh from new GitHub issues
- [ ] Drift detection (new concepts not in ontology)
- [ ] Publish to shared repo for agent access

## Contributors
- **Peng Wu** — domain expert, reviewer
- **Prof** — ontology architect
- **Beaver** — entity extraction from source code, issues, docs
