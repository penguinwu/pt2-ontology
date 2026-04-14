# J1: First Compile

**Question:** How do I get torch.compile to work on my model?

**Issues:** 193 (? open)

**Tier:** symptom

## Entry Symptoms
- **Internal Error / Crash** — Unhandled exception during compilation or execution
- **Graph Break** — Dynamo cannot trace through a code pattern — splits the graph

## Diagnostic Tools
- **tlparse**: TORCH_TRACE + tlparse for first overview

## Routes To
- **J4: Graph Breaks** (when: graph break errors)
- **J5: Dynamic Shapes** (when: recompilation warnings)
- **J8: Custom & Higher-Order Ops** (when: custom op failures)

## Cause Tree
### Internal Error / Crash
- **Backend Bug** — Bug in inductor, triton, or other compilation backend
  - Triton Crash (138 issues)
  - Inductor Wrong Output (63 issues)
  - Cuda Backend Error (53 issues)
  - Numerical Accuracy (30 issues)
  - Codegen Error (10 issues)
- **Distributed Interaction** — Compile conflicts with DDP, FSDP, or tensor parallel
  - Collective Ops Issue (157 issues)
  - Ddp Compile Conflict (92 issues)
  - Fsdp Compile Conflict (86 issues)
  - Dtensor Compile Conflict (22 issues)
  - Parallelism Conflict (15 issues)
- **ABI Incompatibility** — Custom op libraries (flash attention, xformers) not ABI-compatible with PyTorch version

### Graph Break
- **Unsupported Operation** — PyTorch op or Python construct not supported by dynamo
  - Unsupported Introspection (405 issues)
  - Unsupported Builtin Getattr (327 issues)
  - Unsupported System Module (286 issues)
  - Unsupported Context Manager (267 issues)
  - Unsupported Numpy Api (133 issues)
  - Unsupported Property Decorator (130 issues)
  - Unsupported Generator (126 issues)
  - Unsupported Functools (89 issues)
  - Unsupported Random Module (80 issues)
  - Unsupported Autocast (72 issues)
  - Unsupported Jit Script (56 issues)
  - Unsupported Itertools (22 issues)
  - Unsupported Einops (22 issues)
  - Unsupported Collections (20 issues)
  - Unsupported Async (4 issues)
  - fancy_compile_wrapper
- **Data-Dependent Control Flow** — Branching on tensor values (e.g., if x.item() > 0)
  - Conditional Tensor Operation (164 issues)
  - Item In Condition (56 issues)
  - Control Flow Ops (5 issues)
  - Loop Over Tensor Value (5 issues)
  - dynamic_output_shape
  - scalar_return
- **Third-Party Library Call** — Calls to libraries dynamo cannot trace into
  - Numpy Call (428 issues)
  - Huggingface Transformers (274 issues)
  - Vision Library (169 issues)
  - Pillow Call (25 issues)
  - Scipy Call (15 issues)
  - Opencv Call (11 issues)
  - Pandas Call (9 issues)
  - Sklearn Call (3 issues)
  - ABI Incompatibility
- **Custom Autograd Function** — User-defined torch.autograd.Function not traceable
  - Custom Autograd Function (112 issues)
  - Saved Tensor Hooks (33 issues)
  - Double Backward Issue (5 issues)
  - Non-Compliant Custom Operator
- **Tensor Subclass** — Custom tensor subclasses with non-standard behavior
  - Fake Tensor Mode (329 issues)
  - Torch Dispatch Protocol (140 issues)
  - Torch Function Protocol (65 issues)
  - Dtensor Subclass (61 issues)
  - Sparse Tensor Subclass (17 issues)
  - Nested Tensor Subclass (6 issues)
  - Quantized Tensor Subclass (2 issues)
- **Distributed Interaction** — Compile conflicts with DDP, FSDP, or tensor parallel
  - Collective Ops Issue (157 issues)
  - Ddp Compile Conflict (92 issues)
  - Fsdp Compile Conflict (86 issues)
  - Dtensor Compile Conflict (22 issues)
  - Parallelism Conflict (15 issues)

## Resolutions
- **Code Pattern Change** [user_adaptation] — Rewrite code pattern to be compile-friendly (fundamental limitation)
- **Op Replacement** [user_adaptation] — Swap unsupported op for supported equivalent
- **Skip Compilation** [user_workaround] — Exclude region from compilation — avoids problem, doesn't solve it
- **Upstream Fix (PR)** [upstream_fix] — Internal compiler error — needs PyTorch PR
- **Version Upgrade** [upstream_fix] — Bug already fixed in newer PyTorch version

### Specific Cause → Fix
- **dynamic_output_shape** → **enable_capture_ops** [compiler_fix] — Set capture_dynamic_output_shape_ops=True
- **scalar_return** → **enable_capture_ops** [compiler_fix] — Set capture_scalar_outputs=True

