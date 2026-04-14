# J4: Graph Breaks

**Question:** Parts of my model fall back to eager — or it's unexpectedly slow and I don't know why.

**Issues:** 495 (? open)

**Tier:** root_cause

## Entry Symptoms
- **Graph Break** — Dynamo cannot trace through a code pattern — splits the graph
- **torch._dynamo.exc.Unsupported** — Dynamo explicitly doesn't support this construct

## Diagnostic Tools
- **TORCH_LOGS**: TORCH_LOGS=graph_breaks
- **fullgraph**: fullgraph=True to find all breaks

## Routed From
- **J1: First Compile** (when: graph break errors)
- **J2: Performance Diagnosis** (when: graph breaks causing slowdown)
- **J3: Correctness & Debugging** (when: graph break causes incorrect behavior)

## Involves
- **TorchDynamo**
- **Guard System**

## Cause Tree
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

### Specific Cause → Fix
- **dynamic_output_shape** → **enable_capture_ops** [compiler_fix] — Set capture_dynamic_output_shape_ops=True
- **scalar_return** → **enable_capture_ops** [compiler_fix] — Set capture_scalar_outputs=True

