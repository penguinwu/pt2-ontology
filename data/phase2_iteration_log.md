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

## Iteration 3: Priority A closed issues (5-17 comments)

**Sample:** 10 Priority A (closed) issues selected by signal score from refined pool
**Issues:** #92925, #111199, #157363, #146536, #105290, #152425, #133735, #144792, #141548, #90375
**Avg Quality Score:** 8.6/10
**Total New Entities:** 12 (8 symptoms, 3 workarounds, 1 config)

### Findings

**Component distribution:**
- torchdynamo: 6 issues (fake inputs, dynamic scalars, ValueRanges, runtime asserts, weakrefs, DDP)
- user_error: 2 issues (custom op stream, fake kernel strides)
- torchinductor: 1 issue (alignment clone losing mutation)
- aot_autograd: 1 issue (complex scalar backward)

**Quality by issue type:**
- Real compiler bugs with clear fix: 8-10/10 (#92925, #111199, #152425, #133735, #90375)
- User errors with great diagnostic trail: 9/10 (#157363, #146536) — valuable for teaching correct patterns
- Open/in-progress issues: 10/10 (#141548) — richest conversations happen when multiple engineers collaborate over time
- Performance pathology: 8/10 (#144792) — clear symptom + workaround
- Complex number gap: 9/10 (#105290) — systemic gap, not single-issue fix

**Key insight — user errors are high-value extractions:**
Two issues (#157363, #146536) were user errors, but they produced excellent diagnostic signals:
- Partial-zeros output pattern → CUDA stream issue in custom ops
- Fake kernel stride mismatch → silent incorrectness from metadata disagreement
These patterns are exactly what the ontology needs for automated diagnosis.

**New diagnostic technique discovered:**
- `torch._functorch.config.fake_tensor_crossref = "all"` — cross-references fake tensor metadata against concrete tensors, catches stride mismatches (#152425)

### Entity Yield

| Type | Count | Notable |
|------|-------|---------|
| Symptoms | 8 | partial_zeros_output, mutation_lost_on_alignment_clone, weakref_blocks_device_move |
| Workarounds | 3 | fix_custom_op_stream, fix_mark_dynamic_instead, fix_avoid_many_splits |
| Configs | 1 | fake_tensor_crossref |
| Diagnostic tools | 3 | aot_graphs_log, weakref_monkey_patch, minifier_aot_eager |

### Cumulative Stats (30 extractions total)

| Metric | Iter 1 | Iter 2 | Iter 3 | Total |
|--------|--------|--------|--------|-------|
| Issues | 10 | 10 | 10 | 30 |
| Avg quality | 9.2 | 6.8 | 8.6 | 8.2 |
| New symptoms | 9 | 0 | 8 | 17 |
| New workarounds | 7 | 0 | 3 | 10 |
| New configs | 3 | 0 | 1 | 4 |
| Compiler fixes | 5 | 3 | 5 | 13 |
| User errors | 0 | 3 | 2 | 5 |

## Next Iteration Recommendations

1. **Continue Priority A batch**: ~170 remaining Priority A (closed+completed) issues
2. **Process in batches of 10-20**: Iteration 3 quality (8.6) validates this batch size
3. **User errors are valuable**: Don't filter them out — they reveal diagnostic patterns
4. **Consider automating extraction**: 30 manual extractions is enough to define the schema; could prompt an LLM for remaining 350+ issues
5. **Update decision tree**: Add new entry points from iteration 3 findings (custom op stream, fake kernel metadata, device movement)
