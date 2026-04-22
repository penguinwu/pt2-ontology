#!/usr/bin/env python3
"""
Source code validator — checks ontology entities against PyTorch codebase.

Validates that:
1. Component names/paths still exist in the codebase
2. Config flags haven't been renamed or removed
3. Op names are still valid

Usage:
    python source_validator.py [--pytorch-root /path/to/pytorch]

Default pytorch root: ~/projects/pytorch
"""

import json
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

ONTOLOGY_DIR = Path(__file__).parent.parent / "ontology"

# Default pytorch roots to try (last two are Meta-internal devserver fallbacks)
PYTORCH_ROOTS = [
    Path.home() / "projects" / "pytorch",
    Path.home() / "fbsource" / "fbcode" / "caffe2",
    Path.home() / "fbsource",
]


def find_pytorch_root(override=None):
    """Find the PyTorch source root."""
    if override:
        p = Path(override)
        if p.exists():
            return p
        print(f"Warning: specified root {override} doesn't exist", file=sys.stderr)

    for root in PYTORCH_ROOTS:
        if root.exists():
            return root

    return None


def grep_codebase(root, pattern, file_glob="*.py", max_results=5):
    """Search for a pattern in the PyTorch codebase."""
    try:
        result = subprocess.run(
            ["grep", "-rl", "--include", file_glob, "-m", str(max_results), pattern, str(root)],
            capture_output=True, text=True, timeout=30
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def validate_configs(pytorch_root):
    """Check that config flags still exist in the codebase."""
    configs = json.load(open(ONTOLOGY_DIR / "entities" / "configs.json"))
    results = []

    for config in configs:
        config_name = config["name"]
        # Skip env vars — they're referenced differently
        if config_name.startswith("TORCH_"):
            # Search for env var usage
            files = grep_codebase(pytorch_root, config_name)
        else:
            # Search for config attribute
            files = grep_codebase(pytorch_root, config_name)

        results.append({
            "id": config["id"],
            "name": config_name,
            "found": len(files) > 0,
            "file_count": len(files),
            "sample_files": [str(Path(f).relative_to(pytorch_root)) for f in files[:3]],
        })

    return results


def validate_components(pytorch_root):
    """Check that component module paths still exist."""
    components = json.load(open(ONTOLOGY_DIR / "entities" / "components.json"))
    results = []

    for comp in components:
        # Try to find the component by its aliases (which often include module paths)
        found_any = False
        search_terms = [comp["name"]] + comp.get("aliases", [])
        matched_term = None

        for term in search_terms:
            # Skip very generic terms
            if len(term) < 4 or term in ("fx", "hop"):
                continue
            files = grep_codebase(pytorch_root, term, max_results=2)
            if files:
                found_any = True
                matched_term = term
                break

        results.append({
            "id": comp["id"],
            "name": comp["name"],
            "found": found_any,
            "matched_term": matched_term,
            "deprecated": comp.get("deprecated", False),
            "phase": comp.get("phase", 1),
        })

    return results


def validate_ops(pytorch_root):
    """Check that operator names still exist."""
    ops = json.load(open(ONTOLOGY_DIR / "entities" / "ops.json"))
    results = []

    for op in ops:
        files = grep_codebase(pytorch_root, op["name"])
        results.append({
            "id": op["id"],
            "name": op["name"],
            "found": len(files) > 0,
            "file_count": len(files),
        })

    return results


def print_report(config_results, component_results, op_results):
    """Print validation report."""
    print("=" * 60)
    print("SOURCE CODE VALIDATION REPORT")
    print("=" * 60)

    # Configs
    found = sum(1 for r in config_results if r["found"])
    total = len(config_results)
    print(f"\nConfigs: {found}/{total} found in codebase")
    missing = [r for r in config_results if not r["found"]]
    if missing:
        print("  Missing (may be renamed or removed):")
        for r in missing:
            print(f"    - {r['name']} ({r['id']})")

    # Components
    active = [r for r in component_results if not r.get("deprecated") and r.get("phase", 1) == 1]
    found = sum(1 for r in active if r["found"])
    total = len(active)
    print(f"\nComponents (active): {found}/{total} found in codebase")
    missing = [r for r in active if not r["found"]]
    if missing:
        print("  Not found (may need alias update):")
        for r in missing:
            print(f"    - {r['name']} ({r['id']})")

    # Ops
    found = sum(1 for r in op_results if r["found"])
    total = len(op_results)
    print(f"\nOps: {found}/{total} found in codebase")
    missing = [r for r in op_results if not r["found"]]
    if missing:
        print("  Missing:")
        for r in missing:
            print(f"    - {r['name']} ({r['id']})")

    print()


def main():
    override_root = None
    for i, arg in enumerate(sys.argv):
        if arg == "--pytorch-root" and i + 1 < len(sys.argv):
            override_root = sys.argv[i + 1]

    pytorch_root = find_pytorch_root(override_root)
    if not pytorch_root:
        print("Error: PyTorch source not found. Use --pytorch-root PATH", file=sys.stderr)
        sys.exit(1)

    print(f"PyTorch root: {pytorch_root}", file=sys.stderr)

    config_results = validate_configs(pytorch_root)
    component_results = validate_components(pytorch_root)
    op_results = validate_ops(pytorch_root)

    if "--json" in sys.argv:
        print(json.dumps({
            "pytorch_root": str(pytorch_root),
            "configs": config_results,
            "components": component_results,
            "ops": op_results,
        }, indent=2))
    else:
        print_report(config_results, component_results, op_results)


if __name__ == "__main__":
    main()
