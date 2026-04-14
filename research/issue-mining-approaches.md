# Research: Mining Issues to Build Knowledge Bases

**Date:** 2026-04-14 | **For:** PT2 Ontology project

## The Question

How do others extract structured knowledge (ontologies, knowledge graphs, user journeys) from unstructured issue data (GitHub issues, support tickets, forums)?

## Five Patterns We Can Learn From

### 1. SWE-Bench: Issue-PR Pairing as Ground Truth

SWE-Bench built a dataset of 2,294 real problems from 12 Python repos by pairing GitHub issues with their merged PRs. Each pair gives you a natural **symptom → fix** chain with the code diff as evidence.

**Takeaway for us:** PyTorch issues that have linked PRs are gold. The issue description is the symptom, the PR diff is the fix, and the PR description often names the root cause. Beaver can extract these triples at scale.

### 2. Structured Extraction via Function Calling (LangChain Pattern)

LangChain's approach to KG construction:
1. Define your entity types and relationship types as a JSON schema upfront
2. Use LLM function calling to force structured output matching the schema
3. Chunk long documents, extract per-chunk, merge graphs
4. Post-process: deduplicate entities, normalize names, resolve conflicts

**Takeaway for us:** We already have the schema (12 entity types, 14 relationship types). We can prompt an LLM with our `schema.json` + a GitHub issue and ask it to emit entities and relationships in our format. Function calling removes the "parse free text" problem.

### 3. Two-Stage Retrieval + Extraction (API Documentation Paper)

The "Automating API Documentation from Crowdsourced Knowledge" paper (arxiv 2601.08036) used:
1. **Retrieval stage:** Fine-tuned Dense Passage Retrieval to find relevant Stack Overflow posts per API
2. **Extraction stage:** GPT-4o extracts 7 knowledge types (functionality, concept, pattern, directive, performance, environment, alternative)
3. **Validation stage:** LLM self-checks for hallucination (caught 3.7% errors)
4. **Dedup stage:** Summarize across multiple posts to remove redundancy (31.7% reduction)

**Takeaway for us:** Don't try one-shot extraction. Separate finding relevant issues (retrieval) from extracting structured data (extraction) from validating the result. The validation step is critical — 50% of extraction errors were pure hallucination.

### 4. Knowledge-Graph-Driven Fault Diagnosis (MDPI/ACM Papers)

Industrial KG-based fault diagnosis uses this workflow:
- **Construct KG** from logs, code, and issue history
- **Traverse graph** during a fault: symptom → known patterns → root causes → recommended fixes
- **Learn from resolution:** when a fix works, strengthen that path; when it fails, weaken it

Schema pattern: `Issue → affects → Component`, `Issue → similar_to → Issue`, `Issue → resolved_by → Fix`

**Takeaway for us:** Our ontology IS this kind of fault diagnosis graph. The workflow Peng designed (Observe → Diagnose → Identify → Act → Verify) maps directly to graph traversal. We should think about edge weights or confidence scores — not all `resolved_by` edges are equally reliable.

### 5. Ontology Drift: Keeping It Alive

Key insight from the "Ontology Drift" article: knowledge graphs decay when reality changes but the schema doesn't. Signals of drift:
- Rising % of issues that don't fit any existing category ("Other" bucket)
- Query failure rates increasing
- New terminology appearing in issues that has no entity match

**Takeaway for us:** Build monitoring into the ontology. Track what % of incoming issues can be classified into our existing cause tree. When that drops, it means we have ontology gaps. This is a signal to add new entities.

## Recommended Approach for PT2

Based on this research, here's what I'd suggest for our extraction pipeline:

```
Step 1: RETRIEVE — Find relevant PyTorch issues
  - Filter by labels, components, keywords
  - Beaver already has this capability

Step 2: EXTRACT — Structured extraction per issue
  - Prompt LLM with our schema.json as the target format
  - Use function calling to get: symptom, cause, fix, components involved
  - Output: candidate entities + relationships

Step 3: VALIDATE — Cross-check against existing ontology
  - Does this entity already exist? (dedup)
  - Does this relationship conflict with existing ones?
  - Is the extraction supported by the issue text? (hallucination check)

Step 4: MERGE — Incorporate into ontology
  - New entities go to staging, not production
  - Human review for entity additions, auto-merge for new edges on existing entities
  - Track provenance (which issue produced this knowledge)

Step 5: MONITOR — Detect ontology drift
  - What % of new issues map to existing entities?
  - Which journeys have growing "unclassified" counts?
  - Surface these as ontology expansion candidates
```

## Key Insight

The most successful approaches separate **retrieval** from **extraction** from **validation**. One-shot "read this issue and tell me everything" produces hallucinations. The pipeline approach with explicit validation catches errors before they enter the knowledge base.

## Sources

- SWE-Bench (Jimenez et al., 2024) — issue-PR pairing methodology
- "Automating API Documentation from Crowdsourced Knowledge" (arxiv 2601.08036) — 4-stage extraction pipeline
- "Classifying Issues in Open-source GitHub Repositories" (arxiv 2507.18982) — issue taxonomy + ML classification
- LangChain KG construction blog — schema-driven LLM extraction
- "Ontology Drift" (Medium/Graph Praxis) — knowledge graph maintenance
- "Knowledge-Graph-Driven Fault Diagnosis" (MDPI Sensors 2025) — industrial KG fault diagnosis
