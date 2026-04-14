# J6: Compile-Time Performance

**Question:** Compilation takes minutes and my GPU sits idle.

**Issues:** 347 (? open)

**Tier:** root_cause

## Entry Symptoms
- **Slow Compilation** — Compilation takes excessively long (minutes to hours)
- **Compile Timeout** — Compilation exceeds job timeout threshold (e.g., 10min or 30min training job timeout)
- **Compilation OOM** — Out of memory during compilation (not runtime)

## Diagnostic Tools
- **Compile Time Profiler**: TORCH_COMPILE_CPROFILE=1
- **TORCH_COMPILE_DEBUG**: TORCH_COMPILE_DEBUG=1
- **TORCH_LOGS**: TORCH_LOGS=inductor for compilation pipeline details

## Routed From
- **J2: Performance Diagnosis** (when: compilation overhead)

## Involves
- **Compilation Cache**
- **TorchInductor**

## Cause Tree
### Slow Compilation
- **Dynamic Shapes Complexity** — Shape expressions too complex for symbolic reasoning
  - Unbacked Symint (63 issues)
  - Ragged Tensor Shapes (32 issues)
  - Shape Specialization Needed (30 issues)
  - Stride Specialization (4 issues)
- **Excessive Logging/Debug Overhead** — Debug logging (e.g., everstore uploads, graph dumps) causing compile time bloat

## Resolutions
- **Configuration Change** [compiler_fix] — Enable caching, reduce graph size, tune compile options

