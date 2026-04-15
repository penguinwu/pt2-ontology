# Phase 2 Extraction — Iteration Log

## Iteration 1: Top 10 by conversation length (19-31 comments)

**Sample:** 10 issues with the longest conversations
**Avg Quality Score:** 9.2/10
**Total New Entities:** 49

### Findings
- All 10 issues reclassified from "unknown" to meaningful resolution types (100%)
- Long conversations consistently yield high-quality extractions
- Strong entity discovery: avg 4.9 new entities per issue
- 5 torchinductor, 3 torch_export, 1 aot_autograd, 1 torchdynamo

### Limitations
- Selection bias: longest conversations are the easiest to extract from
- Missing fix_prs: extraction didn't capture specific PR numbers even when referenced
- No inter-rater reliability check

## Iteration 2: Stratified sample (5-13 comments)

**Sample:** 3 short (5-6), 4 medium (7-9), 3 long (10-14) — random within strata
**Avg Quality Score:** 6.8/10
**Total New Entities:** 15

### Findings

**Quality drops significantly for shorter conversations:**
- Long (10-14 comments): avg 9.0/10 — comparable to iteration 1
- Short (5-6 comments): avg 8.0/10 — still good when it's a real bug
- Medium (7-9 comments): avg 5.3/10 — worst! Often feature requests or "can I work on this?"

**Conversation length is NOT the quality driver — issue TYPE is:**
- Real compiler bugs with diagnosis: 8-10/10 regardless of length
- Feature requests with discussion: 5-6/10 (no diagnostic content)
- CI/tooling issues: 3/10 (wrong category entirely)
- Environment/packaging issues: 8/10 (simple but clear)

### Key Insight
The main quality signal is whether the conversation contains **diagnostic reasoning** — someone investigating root cause, testing backends, narrowing the bug. Feature requests, "can I work on this?" threads, and CI issues have many comments but no diagnostic content.

## Refinements Applied

### Pre-filters (removed 115/698 = 17% of candidates)
1. **Feature requests** (72): Issues with `### 🚀` body prefix
2. **CI/test infrastructure** (46): Title matches CI/pytest/test infra patterns
3. **Contributor-dominated** (1): 30%+ comments are "can I work on this?"

### Refined candidate pool: 583 issues

### Remaining risks
- Some "bug" issues are actually feature requests in disguise
- Environment issues (broken nightly, package conflicts) are easy to extract but low ontology value
- Stale issues (closed with "no activity") have low signal-to-noise

## Next Iteration Recommendations

1. **Add confidence threshold**: Skip issues where extraction confidence < "medium"
2. **Add entity yield filter**: After extracting, flag issues with 0 new entities for review
3. **Process in priority order**: Sort refined candidates by expected yield:
   - Priority A: closed + completed + 7+ comments (likely resolved bugs) ~180 issues
   - Priority B: open + 7+ comments (may have partial diagnosis) ~100 issues
   - Priority C: closed + stale + 5-6 comments (low expected yield) ~300 issues
4. **Batch size**: Process 20-30 per iteration, audit after each batch
