# J2: Performance Diagnosis

**Question:** My compiled model is slower than eager — or the speedup is disappointing.

**Issues:** 800 (? open)

**Tier:** symptom

## Entry Symptoms
- **Performance Regression** — Compiled code runs slower than eager mode
- **Performance Improvement** — Compiled code is faster than eager but user wants more speedup — suboptimal fusion, kernel selection, or missed optimization opportunities. Distinct from perf_regression (slower than eager).
- **Silent Performance Degradation** — No error but compiled code is slower than eager

## Diagnostic Tools
- **TORCH_LOGS**: TORCH_LOGS=graph_break_count,compilation_metrics
- **tlparse**: TORCH_TRACE + tlparse for full compilation report

## Routes To
- **J4: Graph Breaks** (when: graph breaks causing slowdown)
- **J5: Dynamic Shapes** (when: shape recompilation)
- **J6: Compile-Time Performance** (when: compilation overhead)
- **J7: Performance Optimization** (when: wants more speedup)

## Cause Tree
### Performance Improvement
- **Suboptimal Inductor Heuristics** — Default triton config heuristics (tile sizes, num_warps) produce suboptimal kernel performance
  - Excessive Memory Usage (81 issues)
  - Slow Compilation (43 issues)
  - Slow Triton Kernel (4 issues)
  - Poor Autotuning (1 issues)
- **Automatic Dynamic Shapes** — Dynamo's automatic shape dynamism causing unexpected recompilation or suboptimal code
  - Auto Dynamic Enabled (14 issues)
  - Assume Static False (4 issues)
  - shape_wobble

## Resolutions
- **Configuration Change** [compiler_fix] — Tune mode, backend options, or disable problematic optimizations
- **Configuration Change** [compiler_fix] — Enable max-autotune, tune inductor flags
- **Code Pattern Change** [user_adaptation] — Restructure model for better fusion/codegen

