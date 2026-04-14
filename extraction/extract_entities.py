#!/usr/bin/env python3
"""
Entity extraction from GitHub issues for the PT2 ontology.

Processes issue data (from JSONL files) and extracts structured entities
and relationships by analyzing issue title, body, labels, and comments.

This is a deterministic/heuristic extractor (no LLM required) that covers
common patterns. It complements the label classifier by extracting deeper
entity-level data from issue text.

Usage:
    python extract_entities.py --input extraction/j3_issues.jsonl --journey j3
    python extract_entities.py --input extraction/j6_issues.jsonl --journey j6
    python extract_entities.py --input extraction/j3_issues.jsonl --journey j3 --json
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ONTOLOGY_DIR = Path(__file__).parent.parent / "ontology"


def load_ontology():
    """Load relevant ontology entities for matching."""
    entities = {}
    for etype in ["components", "causes", "symptoms", "configs", "resolutions", "platforms"]:
        path = ONTOLOGY_DIR / "entities" / f"{etype}.json"
        if path.exists():
            data = json.load(open(path))
            entities[etype] = data
    return entities


# --- Patterns for extracting specific entity types ---

# Config flags mentioned in issues
CONFIG_PATTERNS = [
    (re.compile(r'torch\._dynamo\.config\.(\w+)', re.IGNORECASE), 'dynamo'),
    (re.compile(r'torch\._inductor\.config\.(\w+)', re.IGNORECASE), 'inductor'),
    (re.compile(r'TORCHDYNAMO_(\w+)', re.IGNORECASE), 'dynamo_env'),
    (re.compile(r'TORCHINDUCTOR_(\w+)', re.IGNORECASE), 'inductor_env'),
    (re.compile(r"mode=['\"]?(reduce-overhead|max-autotune|default)['\"]?", re.IGNORECASE), 'compile_mode'),
    (re.compile(r'dynamic\s*=\s*(True|False)', re.IGNORECASE), 'dynamic'),
    (re.compile(r'fullgraph\s*=\s*(True|False)', re.IGNORECASE), 'fullgraph'),
    (re.compile(r'backend\s*=\s*["\'](\w+)["\']', re.IGNORECASE), 'backend'),
]

# Error patterns that indicate specific causes
ERROR_CAUSE_PATTERNS = [
    (re.compile(r'graph\s*break', re.IGNORECASE), 'graph_break'),
    (re.compile(r'recompil(?:ation|ing|e)', re.IGNORECASE), 'recompilation'),
    (re.compile(r'guard\s+fail', re.IGNORECASE), 'guard_failure'),
    (re.compile(r'dynamic\s+shape', re.IGNORECASE), 'dynamic_shape_issue'),
    (re.compile(r'shape\s+specializ', re.IGNORECASE), 'shape_specialization'),
    (re.compile(r'fake\s*tensor', re.IGNORECASE), 'fake_tensor_issue'),
    (re.compile(r'meta\s+(?:kernel|impl)', re.IGNORECASE), 'meta_kernel_issue'),
    (re.compile(r'stride\s+mismatch', re.IGNORECASE), 'stride_mismatch'),
    (re.compile(r'decomposition', re.IGNORECASE), 'decomposition_issue'),
    (re.compile(r'autograd.*(?:error|fail|wrong|incorrect)', re.IGNORECASE), 'autograd_issue'),
    (re.compile(r'backward.*(?:error|fail|nan|wrong)', re.IGNORECASE), 'backward_error'),
    (re.compile(r'(?:nan|NaN|inf|Inf)s?\b.*(?:output|result|loss|gradient)', re.IGNORECASE), 'numerical_issue'),
    (re.compile(r'(?:output|result|loss|gradient).*(?:nan|NaN|inf|Inf)', re.IGNORECASE), 'numerical_issue'),
    (re.compile(r'OOM|out\s+of\s+memory|CUDA\s+out\s+of\s+memory', re.IGNORECASE), 'oom'),
    (re.compile(r'(?:segfault|SIGSEGV|SIGIOT|SIGABRT|core\s+dump)', re.IGNORECASE), 'crash'),
    (re.compile(r'internal\s+assert', re.IGNORECASE), 'internal_assertion'),
    (re.compile(r'triton.*(?:error|fail|compile)', re.IGNORECASE), 'triton_issue'),
    (re.compile(r'codegen.*(?:error|wrong|incorrect|bug)', re.IGNORECASE), 'codegen_issue'),
    (re.compile(r'(?:torch\.export|export.*fail)', re.IGNORECASE), 'export_issue'),
    (re.compile(r'cache.*(?:miss|stale|corrupt)', re.IGNORECASE), 'cache_issue'),
    (re.compile(r'compile.*(?:cache|cach)', re.IGNORECASE), 'compile_cache'),
]

# Symptom patterns
SYMPTOM_PATTERNS = [
    (re.compile(r'(?:wrong|incorrect|different)\s+(?:result|output|answer)', re.IGNORECASE), 'wrong_result'),
    (re.compile(r'(?:silent(?:ly)?)\s+(?:wrong|incorrect|produces)', re.IGNORECASE), 'silent_correctness'),
    (re.compile(r'(?:crash|segfault|SIGIOT)', re.IGNORECASE), 'crash'),
    (re.compile(r'(?:error|exception|traceback|RuntimeError)', re.IGNORECASE), 'error_raised'),
    (re.compile(r'(?:slow|takes?\s+(?:long|forever|minutes|hours))', re.IGNORECASE), 'slow_compile'),
    (re.compile(r'performance\s+(?:regression|degradation|drop)', re.IGNORECASE), 'perf_regression'),
    (re.compile(r'(?:hang|stuck|freeze|deadlock)', re.IGNORECASE), 'hang'),
    (re.compile(r'(?:memory\s+leak|OOM|out\s+of\s+memory)', re.IGNORECASE), 'memory_issue'),
    (re.compile(r'(?:flaky|intermittent|non-deterministic)', re.IGNORECASE), 'flaky'),
]

# Resolution patterns in comments/body
RESOLUTION_PATTERNS = [
    (re.compile(r'(?:workaround|work\s*around)\s*(?:is|:)', re.IGNORECASE), 'user_workaround'),
    (re.compile(r'(?:fix(?:ed)?|resolv(?:ed)?)\s+(?:in|by|with)\s+.*(?:pull|PR|#\d)', re.IGNORECASE), 'compiler_fix'),
    (re.compile(r'(?:disable|turn\s+off|set.*False)\s+.*(?:compile|dynamo|inductor)', re.IGNORECASE), 'user_workaround'),
    (re.compile(r'(?:upgrade|update)\s+(?:to|pytorch|torch)', re.IGNORECASE), 'user_adaptation'),
    (re.compile(r'(?:not\s+a\s+bug|expected\s+behavior|by\s+design|won\'t\s+fix)', re.IGNORECASE), 'wontfix'),
]

# Model/framework patterns
MODEL_PATTERNS = [
    (re.compile(r'\b(?:BERT|GPT|LLaMA|Llama|llama)\b'), 'llm_model'),
    (re.compile(r'\b(?:ResNet|VGG|EfficientNet|MobileNet)\b'), 'vision_model'),
    (re.compile(r'\b(?:diffusion|stable\s*diffusion|SDXL)\b', re.IGNORECASE), 'diffusion_model'),
    (re.compile(r'\b(?:transformer|attention)\b', re.IGNORECASE), 'transformer'),
    (re.compile(r'\b(?:vLLM|vllm)\b'), 'vllm'),
    (re.compile(r'\b(?:hugging\s*face|transformers|HF)\b', re.IGNORECASE), 'huggingface'),
    (re.compile(r'\b(?:torchtitan|torchtune|torchao|torchchat)\b', re.IGNORECASE), 'pytorch_ecosystem'),
    (re.compile(r'\b(?:FSDP|DDP|distributed)\b'), 'distributed'),
    (re.compile(r'\b(?:quantiz|float8|int8|int4)\b', re.IGNORECASE), 'quantization'),
]

# Platform patterns
PLATFORM_PATTERNS = [
    (re.compile(r'\b(?:ROCm|AMD|MI\d{3})\b', re.IGNORECASE), 'amd_gpu'),
    (re.compile(r'\b(?:XPU|Intel.*GPU)\b', re.IGNORECASE), 'intel_xpu'),
    (re.compile(r'\bMPS\b'), 'apple_mps'),
    (re.compile(r'\b(?:CPU|cpu)\b.*(?:only|backend|inductor)'), 'cpu'),
    (re.compile(r'\bWindows\b', re.IGNORECASE), 'windows'),
    (re.compile(r'\bmacOS\b', re.IGNORECASE), 'macos'),
    (re.compile(r'\b(?:A100|H100|V100|T4|RTX|NVIDIA)\b', re.IGNORECASE), 'nvidia_gpu'),
]


def extract_from_issue(issue, journey, ontology):
    """Extract entities and relationships from a single issue."""
    text = f"{issue.get('title', '')} {issue.get('body', '') or ''}"
    labels = issue.get('labels', '') or ''

    result = {
        "issue_id": issue["issue_id"],
        "title": issue["title"],
        "journey": journey,
        "state": issue.get("state", ""),
        "existing_entities": [],
        "new_entities": [],
        "relationships": [],
        "configs_mentioned": [],
        "causes_detected": [],
        "symptoms_detected": [],
        "resolutions_detected": [],
        "models_mentioned": [],
        "platforms_detected": [],
    }

    # Extract configs
    seen_configs = set()
    for pattern, config_type in CONFIG_PATTERNS:
        for match in pattern.finditer(text):
            val = match.group(1) if match.lastindex else match.group(0)
            key = f"{config_type}:{val}"
            if key not in seen_configs:
                seen_configs.add(key)
                result["configs_mentioned"].append({
                    "type": config_type,
                    "value": val,
                    "context": text[max(0, match.start()-50):match.end()+50].strip(),
                })

    # Extract causes
    seen_causes = set()
    for pattern, cause_id in ERROR_CAUSE_PATTERNS:
        if pattern.search(text) and cause_id not in seen_causes:
            seen_causes.add(cause_id)
            match = pattern.search(text)
            result["causes_detected"].append({
                "id": cause_id,
                "evidence": text[max(0, match.start()-30):match.end()+80].strip()[:150],
            })

    # Extract symptoms
    seen_symptoms = set()
    for pattern, symptom_id in SYMPTOM_PATTERNS:
        if pattern.search(text) and symptom_id not in seen_symptoms:
            seen_symptoms.add(symptom_id)
            match = pattern.search(text)
            result["symptoms_detected"].append({
                "id": symptom_id,
                "evidence": text[max(0, match.start()-30):match.end()+80].strip()[:150],
            })

    # Extract resolutions
    seen_resolutions = set()
    for pattern, resolution_type in RESOLUTION_PATTERNS:
        if pattern.search(text) and resolution_type not in seen_resolutions:
            seen_resolutions.add(resolution_type)
            match = pattern.search(text)
            result["resolutions_detected"].append({
                "type": resolution_type,
                "evidence": text[max(0, match.start()-30):match.end()+80].strip()[:150],
            })

    # Extract models/frameworks
    seen_models = set()
    for pattern, model_type in MODEL_PATTERNS:
        if pattern.search(text) and model_type not in seen_models:
            seen_models.add(model_type)
            result["models_mentioned"].append(model_type)

    # Extract platforms
    seen_platforms = set()
    for pattern, platform_id in PLATFORM_PATTERNS:
        if pattern.search(text) and platform_id not in seen_platforms:
            seen_platforms.add(platform_id)
            result["platforms_detected"].append(platform_id)

    # Match against existing ontology entities
    for cause in ontology.get("causes", []):
        cause_name = cause.get("name", "").lower()
        cause_aliases = [a.lower() for a in cause.get("aliases", [])]
        all_names = [cause_name] + cause_aliases
        for name in all_names:
            if name and len(name) > 3 and name in text.lower():
                result["existing_entities"].append({
                    "id": cause["id"],
                    "type": "cause",
                    "name": cause.get("name", ""),
                })
                break

    return result


def process_file(input_path, journey):
    """Process a JSONL file of issues and extract entities."""
    issues = []
    with open(input_path) as f:
        for line in f:
            if line.strip():
                issues.append(json.loads(line))

    ontology = load_ontology()
    results = []
    for issue in issues:
        result = extract_from_issue(issue, journey, ontology)
        results.append(result)

    return results


def print_report(results, journey):
    """Print human-readable extraction report."""
    print(f"{'='*60}")
    print(f"EXTRACTION REPORT — {journey.upper()}")
    print(f"{'='*60}")
    print(f"Issues processed: {len(results)}")

    # Aggregate stats
    all_causes = defaultdict(int)
    all_symptoms = defaultdict(int)
    all_configs = defaultdict(int)
    all_models = defaultdict(int)
    all_platforms = defaultdict(int)
    all_resolutions = defaultdict(int)

    for r in results:
        for c in r["causes_detected"]:
            all_causes[c["id"]] += 1
        for s in r["symptoms_detected"]:
            all_symptoms[s["id"]] += 1
        for cfg in r["configs_mentioned"]:
            all_configs[f"{cfg['type']}:{cfg['value']}"] += 1
        for m in r["models_mentioned"]:
            all_models[m] += 1
        for p in r["platforms_detected"]:
            all_platforms[p] += 1
        for res in r["resolutions_detected"]:
            all_resolutions[res["type"]] += 1

    print(f"\n--- Causes (top 15) ---")
    for cause, count in sorted(all_causes.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cause}: {count}")

    print(f"\n--- Symptoms ---")
    for sym, count in sorted(all_symptoms.items(), key=lambda x: -x[1]):
        print(f"  {sym}: {count}")

    print(f"\n--- Configs mentioned (top 15) ---")
    for cfg, count in sorted(all_configs.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cfg}: {count}")

    print(f"\n--- Models/frameworks ---")
    for model, count in sorted(all_models.items(), key=lambda x: -x[1]):
        print(f"  {model}: {count}")

    print(f"\n--- Platforms ---")
    for plat, count in sorted(all_platforms.items(), key=lambda x: -x[1]):
        print(f"  {plat}: {count}")

    print(f"\n--- Resolution types ---")
    for res, count in sorted(all_resolutions.items(), key=lambda x: -x[1]):
        print(f"  {res}: {count}")

    # Issues with no detected causes
    no_causes = [r for r in results if not r["causes_detected"]]
    print(f"\n--- Issues with no detected causes: {len(no_causes)} ---")
    for r in no_causes[:5]:
        print(f"  #{r['issue_id']}: {r['title'][:80]}")

    print()


def main():
    input_path = None
    journey = "unknown"
    output_json = False

    for i, arg in enumerate(sys.argv):
        if arg == "--input" and i + 1 < len(sys.argv):
            input_path = sys.argv[i + 1]
        if arg == "--journey" and i + 1 < len(sys.argv):
            journey = sys.argv[i + 1]
        if arg == "--json":
            output_json = True

    if not input_path:
        print("Usage: python extract_entities.py --input <file.jsonl> --journey <j3|j6>", file=sys.stderr)
        sys.exit(1)

    results = process_file(input_path, journey)

    if output_json:
        print(json.dumps({"journey": journey, "count": len(results), "extractions": results}, indent=2))
    else:
        print_report(results, journey)


if __name__ == "__main__":
    main()
