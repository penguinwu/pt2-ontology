"""Validation for LLM-distilled output.

Two layers:
1. Schema validation — JSON shape (jsonschema lib)
2. Sanity validation — does the entity actually appear in the source text?
   (catches obvious hallucinations)

v0.0 SKELETON. Schema validation is wired; sanity validation is stubbed.
"""
from __future__ import annotations


def validate_against_schema(data, schema: dict) -> None:
    """Raise on schema violation. Uses jsonschema if available; falls back
    to a minimal check if not (so the skeleton runs without extra deps)."""
    try:
        import jsonschema
    except ImportError:
        _minimal_check(data, schema)
        return
    jsonschema.validate(instance=data, schema=schema)


def _minimal_check(data, schema: dict) -> None:
    """Fallback when jsonschema isn't installed.

    Checks: top-level type, item type, required fields on each item,
    and enum membership for declared enums. Not a full JSON-schema impl
    but enough to catch the obvious LLM-output drift cases.
    """
    expected = schema.get("type")
    if expected == "array" and not isinstance(data, list):
        raise ValueError(f"expected list, got {type(data).__name__}")
    if expected == "object" and not isinstance(data, dict):
        raise ValueError(f"expected dict, got {type(data).__name__}")
    if expected != "array":
        return

    item_schema = schema.get("items") or {}
    required = item_schema.get("required") or []
    props = item_schema.get("properties") or {}
    errors = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"[{i}] not a dict")
            continue
        for field in required:
            if field not in item:
                errors.append(f"[{i}] missing required field '{field}'")
        for field, val in item.items():
            spec = props.get(field) or {}
            enum = spec.get("enum")
            if enum is not None and val not in enum:
                errors.append(f"[{i}].{field}={val!r} not in enum {enum}")
    if errors:
        head = "\n  ".join(errors[:10])
        more = f"\n  (+ {len(errors)-10} more)" if len(errors) > 10 else ""
        raise ValueError(f"schema violations:\n  {head}{more}")


def sanity_check(entries: list[dict], source_text: str) -> list[dict]:
    """Filter out entries whose `evidence` field doesn't actually appear in
    source_text. Returns the kept entries; logs the rejected ones.

    v0.0 STUB — implement after the LLM client lands.
    """
    raise NotImplementedError("v0.0 skeleton")
