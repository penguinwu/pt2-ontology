# J9: Export & Serialization

**Question:** I want to save my compiled model so I can load it elsewhere.

**Issues:** 907 (? open)

**Tier:** deployment

## Entry Symptoms
- **Export Failure** — torch.export cannot capture the model graph

## Involves
- **torch.export**
- **AOT Inductor**

## Cause Tree
### Export Failure
- **Missing Decomposition** — Op lacks a decomposition into supported primitives
  - Primtorch Lowering Gap (6 issues)
  - Missing Aten Decomposition (3 issues)
  - Lowering Failure (1 issues)

## Resolutions
- **Code Pattern Change** [user_adaptation] — Rewrite model to meet export constraints (fundamental requirement)

