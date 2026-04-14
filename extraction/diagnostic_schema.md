# Diagnostic Workflow Extraction Schema

Defines what we extract from PT2 issue conversations to build diagnostic decision trees and user-fix shortcuts.

## Two Extraction Paths

### Path A: Deep Diagnosis → Compiler Fix
Issue has a root cause identified in the compiler code, fixed by a PR.
- **Signal**: Issue closed with a linked/referenced PR
- **Extract**: symptom → diagnostic steps → root cause → fix PR → component

### Path B: Symptom → User Fix Shortcut
Issue resolved by a workaround the user can apply, no compiler change needed.
- **Signal**: Issue closed with a workaround comment (config change, code pattern, version upgrade)
- **Extract**: symptom → workaround → conditions where it applies

## Extraction Schema

```json
{
  "issue_number": 172529,
  "path": "compiler_fix|user_workaround|user_adaptation|wontfix|duplicate|stale",

  "symptom": {
    "category": "wrong_result|crash|error|slow_compile|hang|perf_regression|memory_issue",
    "description": "torch.isin returns scalar instead of tensor under compile",
    "error_message": "shape mismatch: expected [3], got []",
    "evidence": "quote from issue body"
  },

  "diagnosis": {
    "steps": [
      {
        "action": "what the diagnostician did",
        "finding": "what they found",
        "tool": "minifier|TORCH_LOGS|bisect|repro_script|manual_inspection|none"
      }
    ],
    "root_cause": {
      "id": "existing_cause_id_or_new",
      "description": "Inductor incorrectly handles broadcasting in isin decomposition",
      "component": "inductor",
      "subcause": "decomposition_issue"
    }
  },

  "resolution": {
    "type": "compiler_fix|upstream_fix|user_workaround|user_adaptation|wontfix|duplicate",
    "description": "Fixed isin decomposition to preserve output shape",
    "fix_pr": "https://github.com/pytorch/pytorch/pull/172531",
    "workaround": {
      "description": "what the user can do",
      "code_snippet": "actual code if provided",
      "config_change": "torch._dynamo.config.X = Y",
      "conditions": "when this workaround applies"
    }
  },

  "participants": {
    "reporter": "xiaowangintel",
    "diagnosticians": ["abhinavgorrepati17"],
    "fixers": ["isuruf"],
    "is_reporter_team": false
  },

  "metadata": {
    "components": ["inductor"],
    "platforms": ["cpu", "cuda", "xpu"],
    "time_to_resolution_days": 8,
    "labels": ["oncall: pt2", "module: inductor", "module: correctness (silent)"]
  },

  "confidence": "high|medium|low",
  "notes": "any special observations"
}
```

## Key Fields to Extract

### For Diagnostic Decision Trees
- `symptom.category` + `symptom.description` → entry point
- `diagnosis.steps[]` → conditional branches ("if you see X, check Y")
- `diagnosis.root_cause.component` + `subcause` → leaf nodes
- `resolution.type` → outcome

### For User-Fix Shortcuts
- `symptom.category` → entry point
- `resolution.workaround.description` → shortcut destination
- `resolution.workaround.conditions` → when to recommend this shortcut
- `resolution.workaround.config_change` → actionable config

## Extraction Priority

### Phase 1: Pattern Frequency (heuristic, no LLM)
Extract from all 3,876 closed issues:
1. Resolution type classification (regex on comments: "fixed by PR", "workaround is", "won't fix", etc.)
2. Workaround extraction (config changes, code snippets in comments)
3. Time-to-resolution calculation

### Phase 2: Deep Extraction (LLM-assisted, targeted)
Extract from top ~100 issues with richest conversations:
1. Full diagnostic step sequences
2. Root cause identification with component mapping
3. Conditional diagnostic logic ("if X then check Y")

## Workaround Pattern Categories
From initial analysis, user workarounds fall into:
1. **Config toggle** — `torch._dynamo.config.X = Y` or env var
2. **Compile mode change** — switch from `reduce-overhead` to `default`
3. **Backend switch** — try `aot_eager` instead of `inductor`
4. **Code restructure** — rewrite model code to be compile-friendly
5. **Version pin** — upgrade/downgrade PyTorch
6. **Disable compile** — fall back to eager (last resort)
7. **Guard adjustment** — mark dynamic dims, use `torch._dynamo.mark_dynamic()`
8. **Op replacement** — use a different op that compiles correctly
