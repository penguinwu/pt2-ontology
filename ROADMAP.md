# PT2 Ontology — Planned Next Steps

> This is a **living document** — it captures what we see as the logical next
> steps *as of today*. Priorities will shift as we learn from each completed
> item. Expect this to evolve; it's a compass, not a contract.

**Last updated:** 2026-04-15

---

## Current State (v0.17.1)

| Layer | Count | Status |
|-------|-------|--------|
| Symptoms | 62 | Complete, visibility-tagged |
| Workarounds | 33 | Complete, visibility-tagged |
| Configs | 40 | Complete, visibility-tagged |
| Experts | 27 | Complete, tagged `internal` |
| Evidence edges | 294 | 11 relationship types, all connected |
| Triage paths | 62 | One per symptom |
| Triage tree entry points | 12 | Error-signature → diagnostic chains |
| Causal chains | 50 | High-level cause/effect |
| Resolution map | 100 | Symptom → fix type |
| Component playbooks | 6 | Per-component diagnostic guides |

**Visibility layer** is in place: three levels (oss / internal / confidential),
classification rules in `ontology/VISIBILITY.md`, export filter in
`tools/export_filter.py`. Due diligence scan complete — unixnames scrubbed,
experts tagged internal.

---

## Priority 1 — First End-to-End Use Case: Doc Audit (Beaver Integration)

**Goal:** Beaver is running a PT2 documentation audit with 8 user journeys and
a 160-issue test suite. The ontology serves as the **completeness rubric** —
ground truth for what topics/symptoms/workarounds the docs should cover.

### Partition of Work

| Concern | Owner | Description |
|---------|-------|-------------|
| Ontology as ground truth | Prof | Maintain and expand the entity/relationship graph |
| Doc audit execution | Beaver | Score docs against user journeys, identify gaps |
| Rubric interface | Prof + Beaver | Define how Beaver queries the ontology |

### Open Design Questions

1. **Packaging format** — How does Beaver consume ontology data?
   - Option A: JSON files checked into a shared repo (simplest)
   - Option B: MCP tool interface (richer, but more infrastructure)
   - Option C: SQLite DB with query interface
   - *Decision needed before implementation.*

2. **Rubric generation** — What does the ontology provide to the audit?
   - Symptom completeness: "Do the docs cover all 62 known symptoms?"
   - Workaround coverage: "For each symptom, is at least one workaround documented?"
   - Config coverage: "Are relevant configs mentioned with each symptom?"
   - Triage path coverage: "Do the docs provide diagnostic steps for each entry point?"
   - Staleness detection: "Are documented workarounds still valid per ontology freshness data?"

3. **Feedback loop** — Beaver's audit findings should flow back to enrich the ontology
   - Gaps found → new entities or relationships to add
   - Stale content found → freshness updates on existing entities

---

## Priority 2 — Additional Data Sources

### 2a. PyTorch Conference Materials (Paris, April 2026)

- **Source:** Public conference talks, slides, demos
- **Visibility:** `oss` (public event — but check for internal-only slides)
- **Value:** New features, best practices, updated guidance that may not be in docs yet
- **Action:** Ingest talk transcripts/slides, extract new symptoms, workarounds, configs

### 2b. PyTorch Compile Q&A Group (Workplace)

- **Source:** Internal Workplace group where engineers ask torch.compile questions
- **Visibility:** Default `internal`; promote individual items to `oss` if content is generic
- **Value:** Real-world user pain points, expert responses with workarounds
- **Scrubbing:** Apply model name and person attribution rules from VISIBILITY.md
- **Action:** Mine Q&A threads for symptom→workaround relationships

### 2c. Internal Chat Groups

- **Source:** Workplace chat channels (oncall, team channels)
- **Visibility:** Default `internal`
- **Value:** Rapid-fire troubleshooting patterns, emerging issues
- **Scrubbing:** Aggressive — replace model names, strip person references
- **Action:** Extract diagnostic patterns and causal relationships

### 2d. Oncall Logs

- **Source:** SEV tickets, oncall handoff notes
- **Visibility:** `internal` or `confidential` depending on content
- **Value:** High-signal failure modes and resolutions under production pressure
- **Action:** Map oncall patterns to existing symptoms, discover new causal chains

---

## Priority 3 — Use Cases (Beyond Doc Audit)

### 3a. Documentation Gap Detection

Given the ontology as ground truth and a set of documentation pages:
- Identify symptoms/workarounds with no corresponding doc coverage
- Rank gaps by severity (frequency of symptom × lack of documented workaround)
- Generate gap reports: "These 15 symptoms have no documentation"

### 3b. Stale Content Flagging

Cross-reference documentation against ontology freshness data:
- Flag docs that reference workarounds marked `deprecated` or `version_limited`
- Identify docs whose advice conflicts with current ontology state
- Priority-rank staleness by user impact

### 3c. Expert Routing

Given a symptom or error signature:
- Look up component ownership via ontology relationships
- Map to expert entities (visibility: internal only)
- Suggest who to escalate to, with context on their scope

### 3d. Triage Assistance (Sentinel Integration)

Rocky's Sentinel project could consume the ontology for automated triage:
- Error signature → triage tree entry point → diagnostic steps
- Symptom identification → workaround suggestions
- Component attribution → oncall routing
- *Requires MCP interface (see below)*

---

## Priority 4 — MCP Interface Design

Make the ontology agent-accessible via MCP (Model Context Protocol) tools.

### Proposed Tools

| Tool | Input | Output |
|------|-------|--------|
| `diagnose(error_message)` | Error text or stack trace | Matched triage entry point, diagnostic steps, likely symptoms |
| `lookup(entity_id)` | Entity ID | Full entity with relationships |
| `find_fix(symptom, component?)` | Symptom ID, optional component | Ranked workarounds and configs |
| `search(query)` | Free-text query | Matching entities and relationships |
| `coverage(doc_url)` | Doc page URL | Ontology topics covered/missing in the doc |

### Architecture Options

1. **File-based MCP server** — reads JSON files directly, minimal infrastructure
2. **SQLite-backed MCP server** — better query performance, supports complex joins
3. **Hybrid** — JSON as source of truth, SQLite as query index (rebuilt on change)

### Considerations

- MCP servers are lightweight — a file-based server could be built quickly
- SQLite enables richer queries (e.g., "all symptoms for torchinductor with known workarounds")
- The ontology is small enough (~135 entities) that file-based is likely sufficient initially
- Could start file-based and migrate to SQLite if query patterns demand it

---

## Priority 5 — Ontology Expansion

### Scope Phases (from project charter)

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | torch.compile (TorchDynamo, TorchInductor, AOT Autograd) | **Active** |
| Phase 2 | torch.export | Not started |
| Phase 3 | Helion | Not started |

### Relationship Enrichment Ideas

- **Temporal edges:** "Symptom X was introduced in version Y, fixed in version Z"
- **Frequency edges:** "Symptom X occurs in N% of compile failures" (from oncall data)
- **Dependency edges:** "Fix A requires config B to be set first"
- **Conflict edges:** "Workaround A and workaround B are mutually exclusive"
- **Regression edges:** "Fix A introduced symptom B as a side effect"

### Entity Type Expansion

- **Error signatures:** Distinct from symptoms — the actual exception text that maps to a symptom
- **PyTorch versions:** Version entities to support temporal relationships
- **Test cases:** Link to specific test files that reproduce symptoms
- **Documentation pages:** Entities representing doc pages, enabling coverage analysis

---

## Completed Milestones

| Version | Date | What |
|---------|------|------|
| v0.14.0 | 2026-04-14 | Phase 2 extraction — 324 issues, 62 symptoms, 33 workarounds, 40 configs |
| v0.15.0 | 2026-04-14 | Relationship mapping — evidence edges, triage tree, component playbooks |
| v0.16.0 | 2026-04-14 | Enriched relationship layer — 294 edges, 62 triage paths, 12 entry points |
| v0.17.0 | 2026-04-15 | Visibility classification layer — privacy gate for internal data sources |
| v0.17.1 | 2026-04-15 | Due diligence scrubbing — strip unixnames, tag experts as internal |

