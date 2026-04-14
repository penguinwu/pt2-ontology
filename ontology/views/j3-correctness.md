# J3: Correctness & Debugging

**Question:** The compiled model gives different results than eager.

**Issues:** 686 (? open)

**Tier:** symptom

## Entry Symptoms
- **Incorrect Output** — Compiled code produces different results than eager mode
- **Numerical Issue** — Numerical drift or precision differences between compiled and eager — distinct from wrong output. May be bitwise parity requirement or acceptable drift threshold.
- **Accuracy Mismatch** — Numerical differences between compiled and eager

## Diagnostic Tools
- **repro_level**: minifier for minimal repro
- **tlparse**
- **switch_backend**: backend='eager'/'aot_eager' to isolate compiler layer

## Routes To
- **J4: Graph Breaks** (when: graph break causes incorrect behavior)

## Cause Tree
### Incorrect Output
- **Backend Bug** — Bug in inductor, triton, or other compilation backend
  - Triton Crash (138 issues)
  - Inductor Wrong Output (63 issues)
  - Cuda Backend Error (53 issues)
  - Numerical Accuracy (30 issues)
  - Codegen Error (10 issues)
- **In-Place Mutation** — In-place ops that violate functional semantics
  - Inplace Arithmetic (82 issues)
  - Inplace Copy (65 issues)
  - Inplace Initialization (31 issues)
  - Inplace Fill (26 issues)
  - Index Assignment (17 issues)
  - Inplace Scatter (14 issues)
  - Inplace Resize (7 issues)
  - Explicit Mutation (1 issues)

### Numerical Issue
- **Backend Bug** — Bug in inductor, triton, or other compilation backend
  - Triton Crash (138 issues)
  - Inductor Wrong Output (63 issues)
  - Cuda Backend Error (53 issues)
  - Numerical Accuracy (30 issues)
  - Codegen Error (10 issues)

## Resolutions
- **Upstream Fix (PR)** [upstream_fix] — Bug in compiler — needs PyTorch PR
- **Configuration Change** [compiler_fix] — e.g., emulate_precision_casts, fallback_random
- **Upstream Fix (PR)** [upstream_fix] — Precision bug in codegen — needs PyTorch PR

