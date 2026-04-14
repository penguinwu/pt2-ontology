# J7: Performance Optimization

**Question:** torch.compile gives me a speedup, but I want more.

**Issues:** 1800 (? open)

**Tier:** root_cause

## Entry Symptoms
- **Performance Improvement** — Compiled code is faster than eager but user wants more speedup — suboptimal fusion, kernel selection, or missed optimization opportunities. Distinct from perf_regression (slower than eager).

## Diagnostic Tools
- **TORCH_LOGS**: TORCH_LOGS=fusion,output_code,perf_hints
- **TORCH_COMPILE_DEBUG**: TORCHINDUCTOR_PROFILE=1 for kernel bandwidth estimates

## Routed From
- **J2: Performance Diagnosis** (when: wants more speedup)

## Involves
- **TorchInductor**
- **Max-Autotune**
- **Triton Heuristics**
- **Inductor Scheduler**

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
- **Configuration Change** [compiler_fix] — Enable max-autotune, tune inductor flags
- **Code Pattern Change** [user_adaptation] — Restructure model for better fusion/codegen

