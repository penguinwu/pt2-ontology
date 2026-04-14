#!/usr/bin/env python3
"""
Drift detection wrapper — runs all validation signals and produces a combined report.

Combines:
1. Ontology consistency (validate.py --check-existing)
2. Entity freshness (freshness.py against recent issues)
3. Source code validation (source_validator.py against PyTorch codebase)
4. Holdout coverage (label_classifier.py against holdout issues)

Usage:
    # Full drift check (requires issue data + PyTorch source)
    python drift_check.py --issues recent_issues.json --holdout holdout_issues.json

    # Quick check (ontology consistency only, no external data needed)
    python drift_check.py --quick

    # Specify PyTorch root
    python drift_check.py --issues issues.json --pytorch-root ~/projects/pytorch
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

VALIDATION_DIR = Path(__file__).parent
ONTOLOGY_DIR = VALIDATION_DIR.parent / "ontology"


def run_script(script_name, args, capture_json=False):
    """Run a validation script and capture output."""
    cmd = [sys.executable, str(VALIDATION_DIR / script_name)] + args
    if capture_json:
        cmd.append("--json")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if capture_json and result.stdout.strip():
            return json.loads(result.stdout)
        return result.stdout
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"error": str(e)}


def check_consistency():
    """Run ontology consistency checks."""
    result = subprocess.run(
        [sys.executable, str(VALIDATION_DIR / "validate.py"), "--check-existing"],
        capture_output=True, text=True, timeout=60
    )
    return {
        "passed": result.returncode == 0,
        "output": result.stdout + result.stderr,
    }


def check_freshness(issues_path):
    """Run entity freshness scan."""
    return run_script("freshness.py", [issues_path, "--raw"], capture_json=True)


def check_source(pytorch_root=None):
    """Run source code validation."""
    args = []
    if pytorch_root:
        args.extend(["--pytorch-root", pytorch_root])
    return run_script("source_validator.py", args, capture_json=True)


def check_holdout_coverage(holdout_path):
    """Run label classifier on holdout issues for coverage measurement."""
    sys.path.insert(0, str(VALIDATION_DIR.parent / "extraction"))
    from label_classifier import build_label_map, classify_dataset

    issues = json.load(open(holdout_path))
    label_map = build_label_map()
    classified = classify_dataset(issues, label_map)

    total = len(classified)
    with_components = sum(1 for c in classified if not c["unclassified"])

    return {
        "total_issues": total,
        "classified": with_components,
        "unclassified": total - with_components,
        "coverage_pct": round(with_components / total * 100, 1) if total > 0 else 0,
    }


def generate_report(consistency, freshness, source, holdout):
    """Generate combined drift report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "schema_version": None,
        "signals": {},
        "action_items": [],
    }

    # Read schema version
    try:
        schema = json.load(open(ONTOLOGY_DIR / "schema.json"))
        report["schema_version"] = schema["meta"]["version"]
    except Exception:
        pass

    # Consistency
    if consistency:
        report["signals"]["consistency"] = {
            "status": "pass" if consistency["passed"] else "fail",
        }
        if not consistency["passed"]:
            report["action_items"].append({
                "severity": "high",
                "signal": "consistency",
                "action": "Fix ontology consistency errors",
                "detail": consistency["output"][:500],
            })

    # Freshness
    if freshness and "error" not in freshness:
        stale = freshness.get("stale", {})
        unmapped = freshness.get("unmapped_labels", {})
        report["signals"]["freshness"] = {
            "referenced_count": len(freshness.get("referenced", {})),
            "stale_count": len(stale),
            "unmapped_label_count": len(unmapped),
        }
        if stale:
            report["action_items"].append({
                "severity": "medium",
                "signal": "freshness",
                "action": f"Review {len(stale)} stale entities for deprecation",
                "entities": list(stale.keys())[:10],
            })
        if unmapped:
            top_unmapped = list(unmapped.items())[:5]
            report["action_items"].append({
                "severity": "low",
                "signal": "freshness",
                "action": f"Consider adding {len(unmapped)} unmapped labels as entities",
                "labels": top_unmapped,
            })

    # Source validation
    if source and "error" not in source:
        configs_missing = [c for c in source.get("configs", []) if not c["found"]]
        comps_missing = [c for c in source.get("components", [])
                        if not c["found"] and not c.get("deprecated") and c.get("phase", 1) == 1]
        ops_missing = [o for o in source.get("ops", []) if not o["found"]]
        report["signals"]["source_validation"] = {
            "configs_found": len(source.get("configs", [])) - len(configs_missing),
            "configs_missing": len(configs_missing),
            "components_found": len(source.get("components", [])) - len(comps_missing),
            "components_missing": len(comps_missing),
            "ops_found": len(source.get("ops", [])) - len(ops_missing),
            "ops_missing": len(ops_missing),
        }
        if configs_missing:
            report["action_items"].append({
                "severity": "medium",
                "signal": "source_validation",
                "action": f"{len(configs_missing)} config flags not found in codebase (may be renamed)",
                "entities": [c["name"] for c in configs_missing],
            })
        if comps_missing:
            report["action_items"].append({
                "severity": "low",
                "signal": "source_validation",
                "action": f"{len(comps_missing)} components not grep-matched (may need alias update)",
                "entities": [c["name"] for c in comps_missing],
            })

    # Holdout coverage
    if holdout:
        report["signals"]["holdout_coverage"] = holdout
        if holdout["coverage_pct"] < 95:
            report["action_items"].append({
                "severity": "high",
                "signal": "holdout_coverage",
                "action": f"Coverage dropped to {holdout['coverage_pct']}% — investigate gaps",
            })

    return report


def print_summary(report):
    """Print human-readable summary."""
    print("=" * 60)
    print(f"DRIFT CHECK REPORT — {report['timestamp'][:10]}")
    print(f"Ontology version: {report.get('schema_version', 'unknown')}")
    print("=" * 60)

    for signal_name, signal_data in report.get("signals", {}).items():
        print(f"\n  {signal_name}: {json.dumps(signal_data)}")

    items = report.get("action_items", [])
    if items:
        print(f"\n--- Action Items ({len(items)}) ---")
        for item in sorted(items, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]]):
            icon = {"high": "!!!", "medium": " ! ", "low": "   "}[item["severity"]]
            print(f"  [{icon}] {item['action']}")
            if "entities" in item:
                for e in item["entities"][:5]:
                    print(f"        - {e}")
    else:
        print("\n  No action items — ontology is healthy!")

    print()


def main():
    quick = "--quick" in sys.argv

    issues_path = None
    holdout_path = None
    pytorch_root = None

    for i, arg in enumerate(sys.argv):
        if arg == "--issues" and i + 1 < len(sys.argv):
            issues_path = sys.argv[i + 1]
        if arg == "--holdout" and i + 1 < len(sys.argv):
            holdout_path = sys.argv[i + 1]
        if arg == "--pytorch-root" and i + 1 < len(sys.argv):
            pytorch_root = sys.argv[i + 1]

    # Always run consistency
    print("Running consistency check...", file=sys.stderr)
    consistency = check_consistency()

    freshness = None
    source = None
    holdout = None

    if not quick:
        if issues_path:
            print("Running freshness scan...", file=sys.stderr)
            freshness = check_freshness(issues_path)

        print("Running source validation...", file=sys.stderr)
        source = check_source(pytorch_root)

        if holdout_path:
            print("Running holdout coverage...", file=sys.stderr)
            holdout = check_holdout_coverage(holdout_path)

    report = generate_report(consistency, freshness, source, holdout)

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print_summary(report)


if __name__ == "__main__":
    main()
