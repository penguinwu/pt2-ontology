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

## Iteration 4: First automated batch (20 issues, Priority A top-comment)

**Sample:** 20 Priority A (closed+completed) issues, selected by highest comment count after filtering dashboards/benchmarks
**Issues:** #93428, #106110, #117045, #123745, #150702, #97693, #127581, #117602, #97077, #93224, #101624, #108079, #102023, #111636, #121069, #130822, #86427, #127677, #138274, #90167
**Avg Quality Score:** 6.0/10
**Total New Entities:** 23 (14 symptoms, 6 workarounds, 3 configs)

### Findings

**Quality distribution (20 issues):**
- High quality (≥7): 10 issues — real compiler bugs with diagnostic paths
- Medium quality (4-6): 7 issues — API guidance, ABI issues, partial diagnostics
- Low quality (<4): 3 issues — pure Q&A with no diagnostic content (#117045, #117602, #90167)

**Component distribution:**
- torch._dynamo: 7 issues (duck sizing, dynamic shapes, scalar ops, RNG, FakeTensor)
- torchinductor: 4 issues (device targeting, index expressions, ABI, quantization)
- aot_autograd: 3 issues (strides, views, export API)
- ddpoptimizer: 3 issues (autocast, dynamic shapes, DDP)
- Q&A (no component): 3 issues

**Key patterns discovered:**
1. **DDP + compile is a rich problem space**: 3 separate issues cover different failure modes (autocast partitioning, dynamic shapes, tracing). DDPOptimizer is being replaced by compiled autograd.
2. **Duck sizing is a current pain point**: #150702 shows real-world diffuser pipeline recompilation from duck sizing — most recent issue in the batch (2025-04).
3. **Index expression generation matters**: #127581 demonstrates 50% perf diff from equivalent index expressions — deep NCU profiling analysis.
4. **Historical patterns are still educational**: Issues like #93428 (stride mismatch) and #86427 (as_strided_scatter) are fixed but reveal diagnostic techniques still applicable today.

**Freshness breakdown of new entities:**
- Living: 6 symptoms, 4 workarounds, 3 configs
- Likely living: 5 symptoms, 1 workaround
- Historical: 7 symptoms, 1 workaround (fixed bugs, still educational)

### Entity Yield

| Type | Count | Notable |
|------|-------|---------|
| Symptoms | 14 | duck_sizing_recompilation, index_expression_perf_regression, nested_tensor_compile_error |
| Workarounds | 6 | fix_disable_duck_shape, fix_rewrite_indexing_narrow, fix_ignore_non_fp_accuracy |
| Configs | 3 | use_duck_shape, TORCHDYNAMO_REPRO_IGNORE_NON_FP, TORCHINDUCTOR_ABI_COMPATIBLE |
| Diagnostic tools | 7 | ncu_warp_stall_sampling, TORCH_LOGS_recompiles, TORCHDYNAMO_REPRO_AFTER |

### Cumulative Stats (50 extractions total)

| Metric | Iter 1 | Iter 2 | Iter 3 | Iter 4 | Total |
|--------|--------|--------|--------|--------|-------|
| Issues | 10 | 10 | 10 | 20 | 50 |
| Avg quality | 9.2 | 6.8 | 8.6 | 6.0 | 7.4 |
| New symptoms | 9 | 0 | 8 | 14 | 31 |
| New workarounds | 7 | 0 | 3 | 6 | 16 |
| New configs | 3 | 0 | 1 | 3 | 7 |
| Compiler fixes | 5 | 3 | 5 | 7 | 20 |
| User errors/Q&A | 0 | 3 | 2 | 7 | 12 |

### Observations on Automated vs Manual Extraction

Iteration 4 is the first "automated" batch — all 20 issues extracted in a single pass from full conversation data, without iterative prompt refinement. Key differences from manual iterations:

1. **Lower avg quality (6.0 vs 8.2)**: Larger batch includes more Q&A and low-signal issues. Manual iterations cherry-picked higher-signal issues.
2. **Higher volume**: 20 issues in one pass vs 10 manually. Entity yield (23 new) is strong despite lower average quality.
3. **Quality filtering needed**: A quality_score threshold of ≥5 would filter the 3 Q&A issues and keep 17 diagnostic-value extractions.
4. **Historical vs living ratio**: More historical entities (7 of 14 symptoms) because automated selection picked high-comment issues regardless of era. Manual iterations were biased toward recent issues.

**Recommendation:** For remaining ~350 candidates, apply quality_score ≥ 5 threshold during entity synthesis. Low-quality extractions are still useful as training data but shouldn't produce ontology entities.

## Iteration 5: Full automated sweep (274 issues, 6 parallel batches)

**Sample:** All 274 remaining closed+completed candidates, processed in 6 parallel batches of 40-74
**Method:** 6 sub-agents processed batches concurrently, reading full conversations from corpus
**Avg Quality Score:** 7.3/10
**Total New Entities:** 17 (10 symptoms, 2 workarounds, 5 configs)

### Findings

**Quality distribution (274 issues):**
- High quality (≥7): 182 issues (66%)
- Medium quality (4-6): 90 issues (33%)
- Low quality (<4): 2 issues (<1%)

**Component distribution (all 324 extractions):**
- torchdynamo: 142 (44%) — dominant component across all issues
- torchinductor: 92 (28%) — second most common
- aot_autograd: 39 (12%)
- torch_export: 12 (4%)
- triton: 10 (3%)
- unknown/other: 29 (9%)

**Resolution types (all 324 extractions):**
- compiler_fix: 225 (69%) — majority of issues are real bugs that got fixed
- user_workaround: 50 (15%) — user-side code changes
- expected_behavior: 23 (7%) — not a bug
- user_adaptation: 12 (4%) — user needed to change approach
- unresolved/other: 14 (4%)

**Entity yield per batch:**
| Batch | Issues | Avg Q | Symptoms | Workarounds | Configs |
|-------|--------|-------|----------|-------------|---------|
| 1 (top conv) | 40 | 7.2 | 0 | 0 | 0 |
| 2 | 40 | 6.8 | 0 | 0 | 4 |
| 3 | 40 | 8.2 | 0 | 0 | 2 |
| 4 | 40 | 5.6 | 10 | 0 | 1 |
| 5 | 40 | 7.6 | 0 | 2 | 2 |
| 6 (tail) | 74 | 8.0 | 0 | 0 | 0 |

**Key observations:**
1. **Entity discovery has plateaued**: Most new entities (symptoms, workarounds) were found in iterations 1-4 (50 manual/semi-manual extractions). The 274 automated extractions added only 10 new symptoms and 2 new workarounds — most diagnostic patterns are already captured.
2. **Configs are the long tail**: 5 genuinely new configs emerged from the sweep — these are less discoverable because they're environment variables or niche settings.
3. **Component distribution is stable**: torchdynamo (44%) + torchinductor (28%) = 72% of all issues. This matches the team's intuition about where users hit problems.
4. **Resolution breakdown validates ontology**: 69% compiler_fix means most issues are real bugs, not user errors. This validates the ontology's focus on compiler behaviors over user patterns.

### Cumulative Stats (324 extractions total)

| Metric | Manual (50) | Automated (274) | Total |
|--------|-------------|-----------------|-------|
| Issues | 50 | 274 | 324 |
| Avg quality | 7.4 | 7.3 | 6.8 |
| Symptoms | 31 | 10 | 41 |
| Workarounds | 16 | 2 | 18 |
| Configs | 7 | 5 | 12 |
| Compiler fixes | 20 | 205 | 225 |
| User errors/Q&A | 12 | 38 | 50 |

### Ontology Final State

| Entity Type | Count |
|-------------|-------|
| Symptoms | 62 |
| Workarounds | 33 |
| Configs | 40 |

## Phase 2 Extraction — Complete

All 324 closed+completed candidates from the refined pool have been extracted. The remaining 89 candidates are open issues (77), NOT_PLANNED closures (7), or reopened (5) — these can be processed in a future pass when they close.

### What's Next

1. **Mine open issues**: 77 open issues may have diagnostic value, especially recent ones
2. **Rebuild ontology**: With stable methodology and full extraction, a clean rebuild from scratch would produce a coherent provenance chain
3. **Decision tree update**: Map new symptoms/workarounds into the triage decision tree
4. **Workplace Q&A extraction**: Internal-only diagnostic patterns from PyTorch Compile Q&A group
5. **Validation refresh**: Re-run config source validation periodically as PyTorch evolves
