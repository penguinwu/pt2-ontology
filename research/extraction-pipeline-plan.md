# PT2 Ontology: Extraction Pipeline Plan

**Date:** 2026-04-14 | **Status:** Draft for Peng's review

## The Problem

We asked Beaver to one-shot extract cause trees from 9,277 GitHub issues. The research says this approach has ~50% error rate on extraction mistakes (the API docs paper found hallucination was the dominant error type). Our evidence:

- **resolved_by data**: all 5 journeys (J4-J8) got identical resolutions — clear template-copy artifact. We correctly rejected this.
- **is_subcause_of data**: higher quality (more constrained task), but unvalidated. Quick spot-check shows plausible structure, but 13 of 89 subcauses have <5 supporting issues — could be noise.

**Bottom line:** The subcause data we merged is probably ~70-80% correct, but we have no systematic way to know which 20-30% is wrong. We need a validation pass, and we need a better pipeline for future extraction.

## Corrective Action: Validate What We Have

Before building the full pipeline, let's validate the v0.6.0 data we already merged.

### Tier 1: Automated sanity checks (Prof does this now)
- [x] Evidence count distribution — done, looks reasonable
- [x] Duplicate detection — none found
- [x] Issue reuse analysis — reuse is legitimate (multi-cause issues)
- [ ] Low-evidence flagging — 13 entries with <5 issues → mark as `confidence: low`
- [ ] Cross-reference with PyTorch source — do entity names match real code constructs?

### Tier 2: Sample-based spot-check (Beaver does this)
- Pick 10 random subcauses across evidence tiers (high/med/low)
- For each: read 2-3 of the example issues and verify the subcause label is correct
- Expected outcome: identify which subcauses are real vs hallucinated
- Scope: ~20-30 issues to read, well within Beaver's capability

### Tier 3: Full validation (future, when pipeline is built)
- Run every subcause through the validation stage (see pipeline below)
- Reject or flag entries that fail validation
- This replaces the manual spot-check

## The Pipeline: 5 Stages

Based on the research patterns, here's what we should build. Each stage is a separate, testable step.

### Stage 1: RETRIEVE (Beaver)

**What:** Find relevant issues for a specific ontology area.

**How:**
- Input: an ontology entity ID (e.g., `unsupported_op`) + a journey (e.g., J4)
- Query: GitHub issues with labels like `oncall: pt2`, filtered by keywords matching the entity
- SWE-Bench pattern: prioritize issues that have linked PRs (gives us ground-truth symptom→fix chains)
- Output: ranked list of issue IDs with relevance scores

**Key improvement over current approach:** Don't dump all 9,277 issues into one extraction call. Retrieve per-entity, so each extraction step has focused context.

### Stage 2: EXTRACT (Beaver or Prof)

**What:** Extract structured entities and relationships from each issue.

**How:**
- Input: one issue + our schema.json + the relevant section of the ontology
- Prompt pattern: "Given this issue and schema, extract: (a) which existing entities are involved, (b) any new entities needed, (c) relationships between them. Use function calling to output in our JSON format."
- LangChain pattern: function calling forces structured output, prevents free-form hallucination
- Output: candidate entities + relationships per issue

**Key improvement:** Per-issue extraction instead of bulk. Each issue gets focused attention. Function calling constrains output format.

### Stage 3: VALIDATE (Prof)

**What:** Cross-check extractions against existing ontology and source material.

**How:**
- **Dedup check:** Does this entity already exist under a different name? (e.g., "numpy integration" vs "numpy_call")
- **Conflict check:** Does this relationship contradict an existing one?
- **Hallucination check:** Re-read the issue — does it actually support the extracted claim?
- **Source cross-reference:** For cause entities, does the named construct exist in PyTorch source code?
- API docs paper pattern: LLM self-check catches 3.7% of errors; manual review catches more

**Key improvement:** This is the stage we completely skipped. Even a simple LLM self-check ("re-read the issue; does it support this extraction?") would catch the worst hallucinations.

### Stage 4: MERGE (Prof)

**What:** Incorporate validated extractions into the ontology.

**How:**
- **Staging area:** New entities go to `entities/staging/` first, not directly into production files
- **Auto-merge rules:** New edges between existing entities can auto-merge if validation passed
- **Human review triggers:** New entity types, entities with <5 evidence, relationship type changes → flag for Peng
- **Provenance tracking:** Each entity/relationship records which issues produced it
- KG fault diagnosis pattern: track confidence scores on edges; strengthen paths that lead to successful resolutions

**Key improvement:** Staging area prevents unvalidated data from entering the production ontology.

### Stage 5: MONITOR (Prof, continuous)

**What:** Detect ontology drift and gaps over time.

**How:**
- **Coverage metric:** For each new batch of issues, what % maps to existing entities? Track this weekly.
- **Unclassified bucket:** Issues that don't match any entity → candidates for new entities
- **Staleness check:** Entities with no new evidence in 3+ months → candidates for deprecation
- **Journey coverage:** Which journeys have the thinnest cause trees? → prioritize next extraction there
- Ontology Drift pattern: rising "Other" percentage is the primary signal

**Key improvement:** Makes the ontology self-improving rather than a one-time artifact.

## Implementation Plan

### Phase 1: Validate + Build Pipeline (today, one session)
- [x] Prof: Cross-reference 13 low-evidence subcause names against PyTorch source — **13/13 verified**
- [x] Beaver: Spot-check 13 subcauses by reading example issues — **5 Yes, 8 Partial, 0 No**
- [x] Diagnosis: entity names are correct, issue curation is the noise source (false-positive regex matches)
- [ ] Prof: Add `confidence` field to subcauses based on evidence + validation
- [ ] Prof: Write extraction prompt template with function calling schema
- [ ] Prof: Build validation script (dedup + conflict + issue-label check)
- [ ] Beaver: Re-mine the 8 Partial subcauses with tighter patterns to clean example_issues
- **Deliverable:** Validated v0.6.1 + working pipeline prototype

### Phase 2: Run pipeline on J3 + J6 (tomorrow, one session)
- [ ] J3 Correctness (symptom tier, 686 issues) — thin cause tree, needs resolved_by edges
- [ ] J6 Compile Time (root-cause tier, 347 issues) — missing causes for compile_oom, compilation_hang
- [ ] J9 Export deliberately excluded — documentation project scope doesn't include it (phase 2)
- [ ] Peng review of staging area
- **Deliverable:** v0.7.0 with pipeline-validated additions for J3 + J6

### Phase 3: Monitoring (scaffolding now, inherently ongoing)
- [ ] Set up weekly coverage metric against new PyTorch issues
- [ ] Build drift detection: % of new issues that map to existing entities
- **Deliverable:** Self-sustaining ontology

### Validation Results (2026-04-14)

Beaver validated all 13 low-evidence subcauses against actual issue content:

| Subcause | Verdict | Issue Quality | Note |
|----------|---------|---------------|------|
| poor_autotuning | Yes | 1/1 clean | |
| batch_size_change | Yes | 1/1 clean | |
| explicit_mutation | Yes | 1/1 clean | |
| quantized_tensor_subclass | Yes | 2/2 clean | |
| missing_aten_decomposition | Yes | 3/3 clean | |
| lowering_failure | Partial | 0/1 | Codegen validation bug, not lowering |
| shape_guard_failure | Partial | 2/3 | #93453 is TensorWithTFOverride |
| cpp_custom_op_registration | Partial | 1.5/3 | #156322 is tracing, not registration |
| sklearn_call | Partial | 1/3 | Noisy regex matches |
| unsupported_async | Partial | 2/4 | Mixed with unrelated graph breaks |
| slow_triton_kernel | Partial | 3/4 | #99807 is AOTAutograd cache |
| assume_static_false | Partial | 2.5/4 | #101151 has no mention of assume_static |
| stride_specialization | Partial | 2/4 | Mixed with capture_scalar / setattr |

**Key insight:** Entity names are all valid (13/13 confirmed against source code). The noise is in issue-to-subcause assignment — false-positive regex matches during retrieval. This is a retrieval problem, not an extraction problem.

## Agent Roles

| Agent | Role | Stages |
|-------|------|--------|
| **Beaver** | Issue retrieval + bulk extraction | 1, 2, spot-check |
| **Prof** | Schema design, validation, merge, monitoring | 2, 3, 4, 5 |
| **Peng** | Review, decision-making, entity approval | 4 (staging review) |

## Open Questions for Peng

1. **Validation depth:** Full re-validation of all 89 subcauses, or just the 13 low-evidence ones?
2. **Confidence threshold:** Below what evidence count should we flag for review? (Currently thinking <5)
3. **Pipeline scope:** Start with one journey (e.g., J4 graph breaks, richest data) or all at once?
4. **Automation level:** How much should auto-merge without human review?
