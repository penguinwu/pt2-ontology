# Extraction Prompt Template

Used by agents (Beaver or Prof) to extract ontology data from a single GitHub issue.
Feed this template + the issue content to an LLM with function calling.

## System Prompt

```
You are extracting structured data from a PyTorch GitHub issue for the PT2 Domain Ontology.

Given a GitHub issue, extract:
1. Which EXISTING entities from the ontology are referenced or involved
2. Any NEW entities that should be added (causes, symptoms, resolutions)
3. Relationships between entities

Rules:
- Only extract what the issue text explicitly supports. Do not infer.
- If unsure whether something applies, mark confidence as "low".
- Use existing entity IDs when possible. Only create new entities for genuinely new concepts.
- For cause entities, name them using snake_case matching PyTorch code constructs.
- Every extraction must cite the specific text from the issue that supports it.
```

## Function Schema

```json
{
  "name": "extract_ontology_data",
  "parameters": {
    "type": "object",
    "properties": {
      "issue_id": {"type": "integer", "description": "GitHub issue number"},
      "journey": {"type": "string", "description": "Primary user journey (j1-j9)"},
      "existing_entities": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "id": {"type": "string"},
            "role": {"type": "string", "enum": ["cause", "symptom", "resolution", "component", "config"]},
            "evidence": {"type": "string", "description": "Quote from issue supporting this"}
          },
          "required": ["id", "role", "evidence"]
        }
      },
      "new_entities": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "id": {"type": "string", "description": "snake_case ID"},
            "type": {"type": "string", "enum": ["cause", "symptom", "resolution", "config"]},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "evidence": {"type": "string", "description": "Quote from issue supporting this"}
          },
          "required": ["id", "type", "name", "description", "evidence"]
        }
      },
      "relationships": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "from": {"type": "string"},
            "type": {"type": "string", "enum": ["causes", "is_subcause_of", "is_symptom_of", "fixed_by", "resolved_by", "diagnosed_by"]},
            "to": {"type": "string"},
            "fix_type": {"type": "string", "enum": ["compiler_fix", "upstream_fix", "user_workaround", "user_adaptation"]},
            "evidence": {"type": "string"}
          },
          "required": ["from", "type", "to", "evidence"]
        }
      },
      "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
      "notes": {"type": "string", "description": "Anything unusual about this issue"}
    },
    "required": ["issue_id", "journey", "existing_entities", "relationships", "confidence"]
  }
}
```

## Context to Include

When calling the extraction, include:
1. The full issue text (title + body + first 5 comments if resolution is discussed)
2. The relevant journey view (e.g., j6-compile-time.md) so the LLM knows what exists
3. The entity lists for the journey's involved types (causes.json filtered to relevant parents)

## Example

For a J6 issue about slow compilation due to excessive Triton kernel autotuning:

```json
{
  "issue_id": 99807,
  "journey": "j6_compile_time",
  "existing_entities": [
    {"id": "slow_compile", "role": "symptom", "evidence": "Compilation takes 45 minutes for a simple model"},
    {"id": "max_autotune", "role": "config", "evidence": "Using mode='max-autotune'"}
  ],
  "new_entities": [],
  "relationships": [
    {"from": "max_autotune", "type": "causes", "to": "slow_compile", "evidence": "max-autotune benchmarks every kernel candidate, causing 45min compile"}
  ],
  "confidence": "high"
}
```
