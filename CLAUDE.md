# CLAUDE.md — PT2 Domain Ontology

## What This Is

A structured domain ontology for PyTorch 2 (torch.compile). Maps symptoms, workarounds, configs, components, and experts into a queryable knowledge graph mined from 6,000+ GitHub issues. Currently scoped to torch.compile (Phase 1); torch.export and Helion are Phase 2.

## Roles

| Who | Role | Responsibilities |
|-----|------|-----------------|
| **Peng Wu** | Project owner | Strategic direction, priority decisions, external coordination |
| **Prof** | Tech lead | Ontology architecture, entity/relationship design, extraction pipeline, quality gates |
| **Beaver** | First user | Consumes ontology as rubric for PT2 doc audit; feeds gap/staleness findings back |
| **Rocky/Sentinel** | Future user | May consume ontology for automated issue triage (Priority 3+) |

Prof owns the ontology structure and data quality. Beaver owns the doc audit methodology. Interface between them is the audit rubric (see `docs/beaver-integration.md`).

## Key Files

| Path | What |
|------|------|
| `ontology/entities/` | Entity JSON files: symptoms (62), workarounds (33), configs (40), experts (27) |
| `ontology/relationships/` | Relationship JSON files: evidence_edges (294), triage_paths, triage_tree, causal_chains, resolution_map, component_playbooks |
| `ontology/schema.json` | Entity/relationship type definitions |
| `ontology/VISIBILITY.md` | Classification rules: oss / internal / confidential |
| `tools/export_filter.py` | Strips non-oss content for public export |
| `tools/generate_rubric.py` | Generates doc audit rubric from ontology |
| `ROADMAP.md` | Living planned next steps (compass, not contract) |
| `METHODOLOGY.md` | Full rebuild guide for the extraction pipeline |
| `data/` | Extraction data (diagnostic_extractions_v2.json, phase2_extractions.json) |
| `extraction/` | Extraction scripts (extract_diagnostics_v2.py, extract_phase2.py) |
| `validation/` | Validation tools (freshness.py, source_validator.py, drift_check.py) |

## Privacy Rules (Critical)

This repo may be shared with external collaborators. Follow these rules strictly:

1. **All entities and edges must have a `visibility` field** — `oss`, `internal`, or `confidential`
2. **No unixnames or real names in oss-tagged content.** Use `engineer_XX` anonymized IDs. The mapping is in the git filter-repo replacement file, not in this repo.
3. **Experts are always `internal`.** The `experts.json` file maps anonymized IDs to components and roles.
4. **Model names from internal workloads are `confidential`.** Replace with generic categories (e.g., "ads model", "ranking model").
5. **When in doubt, classify as `internal`** — easy to promote to oss later, hard to un-publish.
6. **Run `python3 tools/export_filter.py --level oss` before any public sharing** to strip non-oss content and validate no dangling references.

## Ontology Conventions

- **Never delete entities.** Deprecate with `deprecated: true`, `deprecated_reason`, and `deprecated_date`.
- **Every entity needs provenance:** `source`, `evidence_issues`, `freshness` (living/historical/stale).
- **Relationship edges need:** `from`, `type`, `to`, `evidence_issues`, `evidence_count`, `visibility`.
- **Entity IDs are snake_case** (e.g., `duck_sizing_recompilation`, `fix_disable_duck_shape`).
- **Components are lowercase** (e.g., `torchdynamo`, `torchinductor`, `aot_autograd`).

## Git Workflow

- Agents **commit locally**. Peng pushes to GitHub (agents are blocked by 3PAI proxy).
- Commit messages follow: `v0.X.Y: One-line description` for version bumps.
- History has been scrubbed with `git filter-repo` — all engineer names anonymized across all commits.

## Tools

```bash
# Generate doc audit rubric
python3 tools/generate_rubric.py --output audit_rubric.json

# Export oss-only ontology
python3 tools/export_filter.py --level oss --output-dir /tmp/oss-export

# Validate entity freshness
python3 validation/freshness.py

# Run source validation (checks configs exist in PyTorch source)
python3 validation/source_validator.py
```

## What Not To Do

- Don't commit untracked data files (`data/pt2_issues_*.jsonl`) — they contain raw GitHub data and are local-only.
- Don't add new entity types without updating `ontology/schema.json`.
- Don't bypass the visibility classification — every new entity/edge gets a visibility tag.
- Don't reference this project's internal data in public-facing outputs.
