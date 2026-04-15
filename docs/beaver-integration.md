# Beaver Integration — Interface Design

> How Beaver consumes the PT2 ontology as a completeness rubric for the doc audit.

**Status:** Draft — needs Peng + Beaver review  
**Date:** 2026-04-15

---

## Context

Beaver is running a PT2 documentation audit with 8 user journeys and a
160-issue test suite. The ontology serves as **ground truth** — the complete
set of symptoms, workarounds, configs, and diagnostic paths that documentation
should cover. Beaver's job is to score existing docs against this ground truth
and identify gaps.

## Design Principles

1. **Start simple.** The first version should be a static file Beaver can read
   — not an MCP server or database. We can upgrade the interface once the use
   case proves valuable.

2. **Rubric, not raw data.** Beaver doesn't need the full ontology schema. It
   needs a derived view: "here's what the docs should cover, organized by topic."

3. **Bidirectional.** Beaver's findings should flow back. Gaps found → new
   entities or relationships. Stale content → freshness updates.

---

## Interface: The Audit Rubric

A single JSON file (`audit_rubric.json`) that Prof generates from the ontology.
Beaver reads it as input to the doc audit.

### Structure

```json
{
  "version": "1.0",
  "generated": "2026-04-15T10:00:00Z",
  "ontology_version": "v0.17.1",
  "description": "PT2 documentation completeness rubric derived from ontology",

  "topics": [
    {
      "id": "recompilation",
      "name": "Recompilation Issues",
      "description": "torch.compile recompiling the function, cache limit exceeded",
      "component": "torchdynamo",
      "priority": "high",

      "error_signatures": [
        "V*torch/_dynamo/guards.py*[__recompiles] Recompiling function",
        "torch._dynamo.exc.RecompileError",
        "cache_size_limit reached"
      ],

      "symptoms_to_cover": [
        {
          "id": "recompile_warning",
          "name": "Excessive Recompilation Warning",
          "description": "...",
          "subtypes": [
            "duck_sizing_recompilation",
            "dynamic_shape_specialization_on_slice",
            "ddp_dynamic_shape_error",
            "symptom_multiple_cache_entries"
          ]
        }
      ],

      "workarounds_to_document": [
        {
          "id": "fix_disable_duck_shape",
          "name": "Disable Duck Shape",
          "description": "Set use_duck_shape = False",
          "applies_to_symptoms": ["duck_sizing_recompilation"]
        },
        {
          "id": "fix_use_maybe_mark_dynamic",
          "name": "Use maybe_mark_dynamic",
          "description": "Replace mark_dynamic with maybe_mark_dynamic",
          "applies_to_symptoms": ["dynamic_shape_specialization_on_slice"]
        }
      ],

      "configs_to_document": [
        {
          "id": "recompile_limit",
          "description": "Max recompilations before torch.compile gives up"
        },
        {
          "id": "use_duck_shape",
          "description": "Enable duck-shaped tensor tracking"
        }
      ],

      "diagnostic_steps": [
        "Run with TORCH_LOGS=recompiles to see which guard triggered",
        "Check if duck_shape is the cause",
        "Check if DDP + dynamic shapes interaction"
      ],

      "coverage_checklist": [
        "Explains what recompilation is and why it happens",
        "Lists common causes (duck sizing, dynamic shapes, DDP)",
        "Provides diagnostic command (TORCH_LOGS=recompiles)",
        "Documents workarounds for each common cause",
        "Lists relevant config knobs with defaults and effects",
        "Covers subtypes as subsections or linked pages"
      ]
    }
  ],

  "summary": {
    "total_topics": 12,
    "total_symptoms": 62,
    "total_workarounds": 33,
    "total_configs": 40,
    "total_diagnostic_steps": "N"
  }
}
```

### Topics Map to Triage Tree Entry Points

The 12 triage tree entry points become the 12 top-level topics:

| Topic ID | Name | Component | Symptom Count |
|----------|------|-----------|---------------|
| `recompilation` | Recompilation Issues | torchdynamo | ~6 |
| `graph_break` | Graph Breaks | torchdynamo | ~8 |
| `backend_error` | Backend Compiler Errors | torchinductor | ~5 |
| `shape_error` | Shape/Guard Errors | torchdynamo | ~4 |
| `accuracy` | Accuracy / Correctness | aot_autograd | ~5 |
| `performance` | Performance Regression | torchinductor | ~6 |
| `export_issue` | torch.export Issues | torch_export | ~4 |
| `custom_op_issue` | Custom Op Issues | torchdynamo | ~3 |
| `distributed_compile` | Distributed + Compile | torchdynamo | ~4 |
| `memory_issue` | Memory / OOM Issues | torchinductor | ~3 |
| `slow_compilation` | Slow Compilation | torchdynamo | ~4 |
| `silent_incorrectness` | Silent Incorrectness | various | ~3 |

Each topic aggregates:
- Its **related symptoms** (from triage tree) + their subtypes (from `is_subtype_of` edges)
- **Workarounds** linked via `addresses_symptom` and `fixed_by` edges
- **Configs** linked via `involves_config`, `uses_config`, and `relevant_to` edges
- **Diagnostic steps** from the triage tree's `diagnostic_path`
- A **coverage checklist** — concrete items Beaver checks against each doc page

### Orphan Symptoms

Some symptoms don't fall under any triage tree entry point. The rubric includes
an "Other / Uncategorized" section so these aren't missed.

---

## Beaver's Audit Output (Feedback Schema)

Beaver produces an audit report that Prof can consume to improve the ontology.

```json
{
  "version": "1.0",
  "audit_date": "2026-04-XX",
  "rubric_version": "1.0",

  "topic_scores": [
    {
      "topic_id": "recompilation",
      "doc_urls": ["https://pytorch.org/docs/..."],
      "coverage_score": 0.75,
      "checklist_results": [
        {"item": "Explains what recompilation is", "covered": true, "doc_ref": "..."},
        {"item": "Lists common causes", "covered": true, "doc_ref": "..."},
        {"item": "Documents workarounds for each cause", "covered": false, "gap": "Missing fix_disable_duck_shape"}
      ],
      "symptom_coverage": {
        "covered": ["recompile_warning", "ddp_dynamic_shape_error"],
        "missing": ["duck_sizing_recompilation", "symptom_multiple_cache_entries"]
      },
      "staleness_flags": [
        {"entity": "fix_use_maybe_mark_dynamic", "issue": "API renamed in 2.6"}
      ]
    }
  ],

  "summary": {
    "topics_fully_covered": 4,
    "topics_partially_covered": 6,
    "topics_missing": 2,
    "symptoms_documented": 45,
    "symptoms_undocumented": 17,
    "stale_items_found": 3
  }
}
```

---

## Feedback Loop: Audit → Ontology

| Beaver Finding | Ontology Action |
|----------------|-----------------|
| Gap: symptom not documented | Prof flags symptom as `documentation_gap: true` |
| Gap: workaround not documented | Prof adds `doc_status: "undocumented"` to workaround entity |
| Stale: workaround API changed | Prof updates freshness to `stale` with reason |
| New: doc mentions symptom not in ontology | Prof adds new symptom entity |
| New: doc mentions workaround not in ontology | Prof adds new workaround entity |

After each audit cycle, Prof regenerates the rubric with updated coverage status.

---

## Implementation Plan

### Phase 1: Static Rubric (this sprint)

1. **Prof builds `tools/generate_rubric.py`** — reads ontology files, produces
   `audit_rubric.json`
2. **Prof generates first rubric** and shares with Beaver
3. **Beaver runs audit** against rubric, produces audit report
4. **Prof ingests audit report** and updates ontology

Delivery: JSON file in the shared repo or uploaded to GDrive.

### Phase 2: Richer Interface (if needed)

If the static rubric proves limiting (Beaver needs dynamic queries, partial
lookups, etc.), upgrade to one of:
- **MCP server** — `diagnose(error)`, `lookup(entity)`, `coverage(doc_url)`
- **SQLite + query script** — Beaver runs queries against a generated DB

Only build this if Phase 1 reveals concrete limitations.

---

## Open Questions for Peng

1. **Topic granularity** — Are the 12 triage entry points the right level, or
   should topics be finer-grained (per-symptom) or coarser (per-component)?

2. **Beaver's 8 user journeys** — Do they align with our 12 topics, or is
   there a mapping exercise needed? If Beaver's journeys are different from
   our entry points, the rubric should be organized around *her* journeys,
   not ours.

3. **Coverage checklist** — Should Prof generate the checklist items, or
   should Beaver define what she checks for and Prof just supplies the entities?

4. **Delivery mechanism** — Shared repo, GDrive, or delegate the rubric
   directly to Beaver?
