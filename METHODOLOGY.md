# PT2 Ontology — Methodology & Rebuild Guide

This document captures the complete methodology for building the PT2 domain ontology.
When the methodology stabilizes, this is the recipe for a clean rebuild from scratch.

**Why this exists:** The current ontology is a mixture of entities extracted by different
methods at different times. Some entities came from Beaver's initial analysis (v0.6.1),
some from heuristic extraction (v0.8.0), some from Phase 2 LLM-assisted deep extraction
(v0.10.0+), and some were hand-curated. A clean rebuild using the finalized methodology
will produce a more consistent, fully-provenanced ontology.

---

## 1. Data Sources

Each source requires a fetch step, a filter step, and an extraction step.
The ontology is the *union* of entities extracted from all sources.

### 1.1 GitHub Issues (Primary — highest signal)

| Attribute | Value |
|-----------|-------|
| **What** | pytorch/pytorch issues with label `oncall: pt2` |
| **Volume** | ~9,300 issues (as of Apr 2026), growing ~200/month |
| **Signal** | Root causes, diagnostic paths, workarounds, configs, symptoms |
| **Fetch** | `skills/pt2-oss-issues/scripts/fetch.sh` (GitHub API via sudo proxy bypass) |
| **Alt fetch** | Hive table `aml.pytorch_github_issues_metadata` (lacks `state_reason`, comments stale) |
| **Filter** | `skills/pt2-oss-issues/scripts/filter.py` (label-based, see §3.2) |
| **Extract** | Phase 1: `extraction/extract_diagnostics_v2.py` (heuristic) |
| | Phase 2: `extraction/extract_phase2.py` (LLM-assisted deep extraction) |
| **Validate** | `skills/pt2-oss-issues/scripts/validate.py` (freshness + source checks) |

**Key learning:** Issue *type* determines extraction quality, not conversation length.
Feature requests and CI issues score poorly regardless of comment count. Label-based
filtering (using human-curated oncall labels) is far more reliable than regex heuristics.

### 1.2 PyTorch Compile Q&A (Workplace Group)

| Attribute | Value |
|-----------|-------|
| **What** | Internal Q&A group (Meta-internal) |
| **Signal** | User pain points, workaround recipes, config recommendations |
| **Fetch** | `knowledge_filtered_search` MCP tool |
| **Status** | Searchable but not bulk-exported. Not yet systematically mined. |

**What to extract:** User questions → symptom patterns. Team answers → workarounds + configs.
Internal-only entities (e.g., internal model names, proprietary benchmark names) should be tagged `visibility: internal`.

### 1.3 PyTorch Codebase

| Attribute | Value |
|-----------|-------|
| **What** | `~/projects/pytorch/torch/` — _dynamo, _inductor, _functorch, _export (or, on Meta devservers, `~/fbsource/fbcode/caffe2/torch/`) |
| **Signal** | Component hierarchy, config flags, op registry, deprecation status |
| **Fetch** | Direct filesystem access (already on devvm) |
| **Extract** | `validation/source_validator.py` (config verification) |
| | `skills/pt2-oss-issues/scripts/validate.py --check-source` (config existence) |

**What to extract:**
- Config flags: grep `torch._dynamo.config`, `torch._inductor.config`, env vars
- Component hierarchy: import structure → structural relationships
- Op registry: `torch.ops.aten.*` → ops.json

### 1.4 PT2 Core STO Structure (Human-Curated)

| Attribute | Value |
|-----------|-------|
| **What** | Workplace post by Peng Wu — who owns what component |
| **Signal** | Component → owner mappings, team structure, customer relationships |
| **Used in** | v0.7.0 (components.json STO owners, GitHub label mappings) |

### 1.5 Beaver's Initial Analysis (Bootstrap)

| Attribute | Value |
|-----------|-------|
| **What** | Beaver agent's issue analysis from early ontology builds |
| **Signal** | Cause tree (21 top-level + 89 subcauses), initial entity catalog |
| **Used in** | v0.6.1 (initial commit — 272 entities, 310 relationships) |
| **Limitation** | No temporal stamps, no evidence_issues, no provenance tracking |

This was the bootstrap. In a rebuild, these entities would be re-derived from GitHub issues
using the current extraction pipeline, giving them proper provenance.

---

## 2. Schema (What to Extract)

The schema defines the *kinds* of entities and relationships. This is methodology,
not data — it should be stable before a rebuild.

### 2.1 Entity Types (15) — current as of v0.17.1

| Type | Count | Source | Provenance Status |
|------|------:|--------|-------------------|
| causes | 118 | Beaver bootstrap + heuristic extraction | **Needs rebuild** — no evidence_issues |
| symptoms | 62 | Mixed: 40 with evidence_issues (Phase 2), 22 from bootstrap | **Partial** — 22 still need backfill |
| components | 43 | STO structure + codebase | Well-provenanced |
| configs | 40 | Mixed: codebase grep + Phase 2 extraction | Source-validated; only 8 carry evidence_issues |
| user_fix_shortcuts | 33 | Phase 2 extraction | Fully provenanced |
| experts | 27 | STO structure | Stable |
| failure_modes | 17 | Bootstrap | **Needs rebuild** |
| resolutions | 14 | Bootstrap (categories: config_change, code_rewrite, etc.) | Stable as type taxonomy |
| platforms | 10 | Manual curation | Stable |
| ops | 9 | Codebase | Stable |
| user_journeys | 9 | Manual design (J1-J9) | Stable |
| ecosystem | 8 | Manual curation | Stable |
| backends | 6 | Manual curation | Stable |
| optimizations | 5 | Manual curation | Stable |
| deprecated_components | 4 | Historical record | Stable |

**Total: 405 entities.** A clean rebuild would primarily benefit causes (118), the 22 unprovenanced symptoms, and the 32 unprovenanced configs.

### 2.2 Relationship Types (16)

Structural, diagnostic, resolution, journey, lifecycle (`replaced_by`, added v0.17.1), platform, and evidence-weighted edges. See `ontology/schema.json` for the full type catalog.

The `replaced_by` edge type (added v0.17.1) supports doc-audit deprecation discovery: a stale doc reference can be resolved to its successor entity with `since_version` and provenance.

### 2.3 Phase 2 Extraction Schema

Each deep extraction produces:
```json
{
  "root_cause": {"component", "mechanism", "trigger", "confirmed_by"},
  "diagnostic_path": [{"step", "action", "result", "conclusion"}],
  "resolution": {"type", "fix_prs", "workaround_configs", "description"},
  "new_entities": {"symptoms", "workarounds", "configs", "diagnostic_tools"},
  "quality_score": 0-10,
  "confidence": "high|medium|low"
}
```

Quality scoring rubric:
- Root cause completeness (0-2)
- Diagnostic path depth (0-2)
- Resolution clarity (0-2)
- Entity yield (0-2)
- Confidence level (0-2)

---

## 3. Pipeline (How to Extract)

### 3.1 Fetch

```
GitHub API → pytorch-issues-pt2-all.json (9,300 issues with inline comments)
```

Script: `skills/pt2-oss-issues/scripts/fetch.sh`
- On Meta devservers, GitHub API access is wrapped in a sudo + internal HTTP proxy bypass; on a standard machine, `gh` works directly
- Date-range batching to work around GitHub's 1,000-result cap
- Comments embedded inline (no separate comments file)
- Incremental fetch with `--since` for updates

### 3.2 Filter

```
9,300 issues → ~7,300 Phase 1 eligible → ~400 Phase 2 candidates
```

Script: `skills/pt2-oss-issues/scripts/filter.py`

Filter stages (all label-based, using human-curated oncall labels):

| Stage | Filter | Excluded | Why |
|-------|--------|----------|-----|
| 1 | Phase 1 resolution | Issues already classified by heuristics | Avoid re-extraction |
| 2 | Min comments | <5 comments | Not enough diagnostic signal |
| 3 | Export labels | `oncall: export`, `export-triaged` | Phase 2 scope |
| 4 | Feature labels | `feature`, `enhancement`, 🚀 body | Not diagnostic |
| 5 | CI/Test labels | `module: flaky-tests`, `module: ci` | Infrastructure |
| 6 | Non-compile | `oncall: distributed`, `oncall: jit` | Different domain |
| 7 | Platform labels | `module: rocm`, `module: xpu`, `module: mps`, Windows, macOS | Phase 2 HW scope |
| 8 | Process labels | `good first issue`, `hackathon`, `skipped` | No signal |
| 9 | Docs/Build | `module: docs`, `module: binaries` | Not bugs |
| 10 | Dashboard titles | "tracker", "dashboard", "pass rate" | Meta-issues |

**Key learning:** Label-based filtering is far more reliable than regex heuristics.
Labels are human-curated by oncalls over multiple years.

Filtered-out sets are preserved for future phases:
- Export issues → Export sub-ontology (Phase 2)
- Platform issues → Hardware backend user journeys (Phase 2)

### 3.3 Phase 1 Extraction (Heuristic)

```
~7,300 issues → resolution type + symptom class + component guess
```

Script: `extraction/extract_diagnostics_v2.py`
- Deterministic (no LLM) — parses issue text for patterns
- Classifies resolution type: compiler_fix, user_workaround, user_adaptation, stale, etc.
- Extracts: causes, symptoms, configs, platforms, model mentions
- Output: `data/diagnostic_extractions_v2.json`

### 3.4 Phase 2 Extraction (LLM-Assisted Deep)

```
~400 candidates → structured extractions (root cause, diagnostic path, entities)
```

Script: `extraction/extract_phase2.py`
- Reads full issue conversation (body + all comments)
- Produces structured extraction per the Phase 2 schema (§2.3)
- Batch processing with signal scoring to prioritize high-yield issues
- Iterative: extract batch → score quality → refine filters → repeat

Priority ordering for batch selection:
- Priority A: closed + completed (likely resolved bugs — highest signal)
- Priority B: open issues (may have partial diagnosis)
- Priority C: other closed (stale, wontfix — lower signal)

Signal scoring formula: `label_overlap × 2 + symptom_variety + conversation_length / 5`

**Phase 2 status (as of v0.17.1):** 324 issues processed, yielding 62 symptoms, 33 user fix shortcuts, 40 configs across multiple iterations. Average extraction quality 8+/10. Phase 2 has reached diminishing returns on the current GitHub corpus — next signal sources are Workplace Q&A and oncall logs (see Priority 2 in ROADMAP).

### 3.5 Entity Synthesis

After each extraction batch:
1. Collect `new_entities` from all extractions in the batch
2. Deduplicate against existing ontology entities
3. Add new entities to the appropriate JSON files with `evidence_issues` references
4. Run `validate.py --check-source --update` to stamp freshness

### 3.6 Validation

```
All entities → freshness classification + source verification
```

Script: `skills/pt2-oss-issues/scripts/validate.py`

Checks:
- **Temporal**: Maps evidence issue dates → PyTorch version eras
- **Source**: Greps the PyTorch source tree for config names (--check-source)
- **Freshness**: living / likely_living / historical / uncertain / base

Classification rules:
- Evidence from PT 2.5+ → living
- Evidence from PT 2.3-2.4 → likely_living
- Evidence from PT ≤2.2 with compiler fix → historical
- Diagnostic techniques → always living (version-independent)
- Configs confirmed in source → living regardless of evidence age
- `FRESHNESS_OVERRIDES` dict for edge cases requiring human judgment

---

## 4. Provenance Requirements

Every entity in a rebuilt ontology must have:

```json
{
  "id": "entity_id",
  "provenance": {
    "source": "github_issues | workplace_qa | codebase | manual",
    "extraction_method": "phase1_heuristic | phase2_llm | source_grep | manual",
    "pipeline_version": "v0.12.0",
    "extracted_date": "2026-04-14",
    "evidence_issues": [12345, 67890]
  },
  "temporal": {
    "first_seen_date": "2023-03-15",
    "last_seen_date": "2025-10-16",
    "first_seen_version": "2.0",
    "last_seen_version": "2.5"
  },
  "freshness": {
    "status": "living | historical | uncertain",
    "reason": "...",
    "classified_date": "2026-04-14"
  }
}
```

**What's missing in the current ontology (v0.17.1):**
- 22 symptoms lack `evidence_issues` (from Beaver bootstrap)
- 32 configs lack `evidence_issues` (from codebase grep, no issue linkage)
- 118 causes lack `evidence_issues` (from Beaver bootstrap)
- No entity has `provenance.source` or `provenance.extraction_method` yet — `freshness` is the only structured provenance field currently populated

The `lifecycle` field (added v0.17.1) is a new structured provenance surface — when status transitions to `deprecated` or `removed`, it captures `since_version` plus `provenance: {type, ref, id}`.

---

## 5. Rebuild Sequence

When the methodology is finalized, rebuild in this order:

### Step 1: Fresh data fetch
```bash
bash skills/pt2-oss-issues/scripts/fetch.sh  # Full GitHub corpus
# Also: bulk export Workplace Q&A (script TBD)
# Also: snapshot PyTorch source configs + components
```

### Step 2: Stable entities (no extraction needed)
- Components → from STO structure + codebase import hierarchy
- Platforms → manual (10, stable)
- Backends → manual (stable)
- Experts → from STO structure
- User journeys → manual design (J1-J9)

### Step 3: Filter candidates
```bash
python skills/pt2-oss-issues/scripts/filter.py --stats  # Review distribution
python skills/pt2-oss-issues/scripts/filter.py           # Generate candidates
```

### Step 4: Phase 1 extraction (all issues)
```bash
python extraction/extract_diagnostics_v2.py  # Heuristic extraction
```

### Step 5: Phase 2 extraction (filtered candidates)
```bash
python extraction/extract_phase2.py --batch 20 --resume  # Iterative deep extraction
```
Process in batches of 10-20. Score quality after each batch.
Continue until diminishing entity yield (<2 new entities per batch).

### Step 6: Entity synthesis
Merge all extracted entities. Deduplicate. Add provenance tags.

### Step 7: Validation
```bash
python skills/pt2-oss-issues/scripts/validate.py --check-source --update
```

### Step 8: Relationship extraction
- Structural: component hierarchy from codebase
- Diagnostic: symptom → cause → resolution from Phase 2 extractions
- Resolution: issue → fix PR from `extraction/pr_linker.py`
- Evidence-weighted: cause → symptom frequency from Phase 1 extraction

### Step 9: Quality check
- Holdout coverage test on recent issues
- Drift detection against previous ontology version
- Freshness report

---

## 6. Methodology Evolution Log

| Version | Date | What Changed |
|---------|------|-------------|
| v0.6.1 | pre-Apr 2026 | Initial ontology from Beaver's analysis. No provenance. |
| v0.7.0 | pre-Apr 2026 | STO owner mappings, GitHub label mappings for components |
| v0.8.0 | pre-Apr 2026 | Heuristic entity extraction, PR linker, expert mapping |
| v0.9.0 | Apr 2026 | Diagnostic workflows, user-fix shortcuts, decision tree |
| v0.10.0 | Apr 14, 2026 | Phase 2 LLM extraction pipeline, full corpus processing |
| v0.11.0 | Apr 14, 2026 | Label-based filtering skill (filter.py), iteration 3 extraction |
| v0.12.0 | Apr 14, 2026 | Validation framework: freshness, version-stamping, source checks |
| v0.14.0 | Apr 14, 2026 | Phase 2 extraction — 324 issues, 62 symptoms, 33 workarounds, 40 configs |
| v0.15.0 | Apr 14, 2026 | Relationship mapping — evidence edges, triage tree, component playbooks |
| v0.16.0 | Apr 14, 2026 | Enriched relationship layer — 294 evidence edges, 62 triage paths |
| v0.17.0 | Apr 15, 2026 | Visibility classification layer (oss / internal / confidential) |
| v0.17.1 | Apr 15, 2026 | Due-diligence scrubbing; (Apr 21) schema sync, lifecycle field, replaced_by |

### Key Methodology Insights (Learned Through Iteration)

1. **Issue type > conversation length** for extraction quality. Feature requests score poorly regardless of comment count.
2. **Label-based filtering >> regex heuristics.** Oncall labels are human-curated over years — use them.
3. **User errors are high-value extractions.** They reveal diagnostic *patterns* (e.g., "partial zeros = check CUDA stream").
4. **Temporal stamping is essential.** Without it, you can't distinguish living entities from historical artifacts.
5. **Source validation is cheap and high-value.** A single grep confirms whether a config still exists. Do it after every batch.
6. **The methodology is part of the output.** Document it as you go, not after the fact.

---

## 7. Open Questions

- **Workplace Q&A extraction**: Not yet systematically mined. Needs a bulk export + extraction pipeline.
- **Automated Phase 2 extraction**: 30 manual extractions define the schema well enough to prompt an LLM for the remaining ~350 candidates. Worth building?
- **Cross-source entity dedup**: When the same symptom appears in GitHub issues and Workplace Q&A, how to merge evidence?
- **Rebuild trigger**: When is the methodology "stable enough" to justify a full rebuild? Current proposal: after Workplace Q&A is integrated and Phase 2 extraction reaches diminishing returns.
