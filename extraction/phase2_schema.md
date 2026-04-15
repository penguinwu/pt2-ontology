# Phase 2: LLM-Assisted Deep Extraction Schema

## Purpose

Phase 1 heuristics classify 54.4% of closed issues into known resolution types. Phase 2 uses LLM analysis on the remaining 698 issues with 5+ comments where heuristics returned "unknown." These issues have rich diagnostic conversations that contain signal the regex patterns miss.

## What Phase 2 Extracts (Beyond Phase 1)

### 1. Root Cause Chain
The causal chain from user-reported symptom to underlying cause.

```json
{
  "root_cause": {
    "component": "torchdynamo | torchinductor | aot_autograd | ...",
    "mechanism": "Free-text: what specifically went wrong",
    "trigger": "What user code/pattern triggered it",
    "confirmed_by": "How root cause was confirmed (minifier, bisect, code reading, ...)"
  }
}
```

### 2. Diagnostic Reasoning Path
The step-by-step diagnostic process from the conversation.

```json
{
  "diagnostic_path": [
    {"step": 1, "action": "Tried aot_eager backend", "result": "Error disappeared", "conclusion": "Bug is in Inductor, not Dynamo"},
    {"step": 2, "action": "Ran minifier", "result": "Reduced to 20-line repro", "conclusion": "Isolated to conv2d fusion"},
    ...
  ]
}
```

### 3. Resolution Detail
Richer than Phase 1's single label.

```json
{
  "resolution": {
    "type": "compiler_fix | user_workaround | user_adaptation | wontfix | stale | duplicate",
    "description": "Free-text description of what resolved it",
    "fix_prs": [12345],
    "workaround_configs": ["torch._inductor.config.foo = False"],
    "version_fixed": "2.4.0 | nightly | specific commit",
    "user_action_required": true/false
  }
}
```

### 4. New Ontology Entities Discovered
Patterns not yet in the ontology.

```json
{
  "new_entities": {
    "new_configs": ["config.name — what it does"],
    "new_symptoms": ["symptom pattern not in current taxonomy"],
    "new_workarounds": ["workaround not in user_fix_shortcuts.json"],
    "new_diagnostic_tools": ["tool/technique not in current patterns"]
  }
}
```

## Extraction Prompt Template

```
You are analyzing a PyTorch torch.compile (PT2) GitHub issue to extract structured diagnostic information for a domain ontology.

Issue #{number}: {title}
State: {state} | State Reason: {state_reason}
Labels: {labels}
Created: {created_at} | Closed: {closed_at}

--- Issue Body ---
{body}

--- Comments ({n} total) ---
{formatted_comments}

Extract the following in JSON:
1. root_cause: {component, mechanism, trigger, confirmed_by}
2. diagnostic_path: [{step, action, result, conclusion}]
3. resolution: {type, description, fix_prs, workaround_configs, version_fixed, user_action_required}
4. new_entities: {new_configs, new_symptoms, new_workarounds, new_diagnostic_tools}
5. confidence: high/medium/low with brief justification
```

## Processing Strategy

- **Priority 1:** 698 issues with unknown resolution + 5+ comments
- **Priority 2:** 782 issues with classified resolution + 10+ comments (validate and deepen)
- **Batch size:** 20-50 issues per session
- **Quality check:** Spot-check 10% of extractions against original conversations

## Output

Append to `diagnostic_extractions_v2.json` with additional `phase2` field:
```json
{
  "issue_number": 12345,
  "...phase1_fields...",
  "phase2": {
    "root_cause": {...},
    "diagnostic_path": [...],
    "resolution": {...},
    "new_entities": {...},
    "confidence": "high",
    "extracted_by": "llm",
    "extracted_at": "2026-04-14"
  }
}
```
