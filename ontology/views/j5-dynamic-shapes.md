# J5: Dynamic Shapes

**Question:** My model recompiles every time the input shape changes.

**Issues:** 1061 (? open)

**Tier:** root_cause

## Entry Symptoms
- **Excessive Recompilation** — Too many guard mismatches cause repeated compilation
- **Recompilation Warning** — torch._dynamo hit recompilation limit

## Diagnostic Tools
- **TORCH_LOGS**: TORCH_LOGS=recompiles,guards,dynamic
- **TORCH_COMPILE_DEBUG**: TORCH_COMPILE_DEBUG=1 for detailed shape analysis

## Routed From
- **J1: First Compile** (when: recompilation warnings)
- **J2: Performance Diagnosis** (when: shape recompilation)

## Involves
- **Dynamic Shapes**
- **Guard System**

## Cause Tree
### Excessive Recompilation
- **Guard Mismatch** — Input doesn't match cached guards — triggers recompile
  - Cache Miss Recompile (444 issues)
  - Shape Guard Failure (3 issues)
  - unspecialized_int
  - Automatic Dynamic Shapes
- **Dynamic Shapes Complexity** — Shape expressions too complex for symbolic reasoning
  - Unbacked Symint (63 issues)
  - Ragged Tensor Shapes (32 issues)
  - Shape Specialization Needed (30 issues)
  - Stride Specialization (4 issues)

## Resolutions
- **Configuration Change** [compiler_fix] — Adjust dynamic shapes, recompile_limit, or guard config

### Specific Cause → Fix
- **shape_wobble** → **use_dynamic_sources** [compiler_fix] — Declare dynamic sources upfront to avoid recompilation
- **shape_wobble** → **reset_dynamo** [compiler_fix] — Reset cache before benchmarking
- **unspecialized_int** → **allow_unspec_int** [compiler_fix] — Set allow_unspec_int_on_nn_module=True

