#!/usr/bin/env python3
"""
Ontology validation script — checks freshness, source presence, and staleness
of all entities in the PT2 ontology.

Usage:
    python validate.py                    # Full validation report
    python validate.py --check-source     # Also grep PyTorch source for configs
    python validate.py --update           # Update freshness classifications in entity files
    python validate.py --stale-only       # Only show stale/uncertain entities
    python validate.py --stats            # Summary statistics only

Requires:
    - Corpus file: ../../data/ (relative to project root)
    - Entity files: ../../ontology/entities/
    - PyTorch source: ~/projects/pytorch/torch/ (for --check-source).
      On Meta devservers, ~/fbsource/fbcode/caffe2/torch/ is also auto-detected.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Resolve paths relative to project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ENTITY_DIR = PROJECT_ROOT / "ontology" / "entities"

# Default PyTorch source roots (last is a Meta-internal devserver fallback)
_PYTORCH_CANDIDATES = [
    Path.home() / "projects" / "pytorch" / "torch",
    Path.home() / "fbsource" / "fbcode" / "caffe2" / "torch",
]
PYTORCH_SOURCE = next((p for p in _PYTORCH_CANDIDATES if p.exists()), _PYTORCH_CANDIDATES[0])

# PyTorch release dates for version mapping
PT_VERSIONS = [
    ("2.0", "2023-03-15"),
    ("2.1", "2023-10-04"),
    ("2.2", "2024-01-30"),
    ("2.3", "2024-04-24"),
    ("2.4", "2024-07-24"),
    ("2.5", "2024-10-16"),
    ("2.6", "2025-01-29"),
    ("2.7", "2025-04-23"),
]

# Entity files to validate
ENTITY_FILES = {
    "symptoms": ENTITY_DIR / "symptoms.json",
    "workarounds": ENTITY_DIR / "user_fix_shortcuts.json",
    "configs": ENTITY_DIR / "configs.json",
}

# Manual overrides for entities that need human judgment
# Format: entity_id -> (status, reason)
FRESHNESS_OVERRIDES = {
    # Diagnostic techniques are always living
    "fix_aot_eager_isolation": ("living", "Diagnostic technique — always valid"),
    "fix_pretrained_weights_verification": ("living", "Diagnostic technique — always valid"),
    "model_instability_false_alarm": ("living", "Diagnostic pattern is timeless"),
    # Complex number issues still active despite old evidence
    "complex_scalar_backward_error": ("living", "Complex compilation issues still active in 2026"),
    # Configs confirmed in source — living despite old evidence
    "fix_disable_autotune_cache": ("living", "Config autotune_local_cache confirmed in source. Cache staleness ongoing."),
    "fix_assume_static_by_default": ("living", "Config confirmed in source. Valid fallback for dynamic shape issues."),
    "fix_clone_gradient_hook": ("uncertain", "max_autotune gradient issues may have been addressed."),
    "fix_disable_ddp_optimizer": ("uncertain", "DDPOptimizer reworked since PT 2.0. Config exists but use case changed."),
    # Specific bugs that were fixed
    "delayed_nan": ("historical", "Original NaN collapse bug fixed in PT 2.0"),
    "dynamic_scalar_regression": ("historical", "torch.add out= + dynamic alpha fixed in PT 2.1"),
    "fix_mark_dynamic_instead": ("historical", "Specific dynamic alpha bug fixed"),
}


def date_to_version(date_str):
    """Map a date string to the PyTorch version era."""
    if not date_str:
        return None
    for i in range(len(PT_VERSIONS) - 1, -1, -1):
        if date_str >= PT_VERSIONS[i][1]:
            return PT_VERSIONS[i][0]
    return "pre-2.0"


def load_corpus_dates():
    """Load issue dates from the corpus."""
    corpus_files = list((Path.home() / "projects" / "pt2-github-issues").glob("pytorch-issues-pt2*.json"))
    if not corpus_files:
        print("WARNING: No corpus file found. Temporal validation skipped.", file=sys.stderr)
        return {}

    with open(corpus_files[0]) as f:
        corpus = json.load(f)

    dates = {}
    for issue in corpus:
        n = issue["number"]
        dates[n] = {
            "created": issue.get("createdAt", "")[:10],
            "closed": issue.get("closedAt", "")[:10] if issue.get("closedAt") else None,
            "state": issue.get("state", ""),
        }
    return dates


def compute_temporal(evidence_issues, issue_dates):
    """Compute temporal metadata from evidence issues."""
    dates = []
    any_open = False
    for n in evidence_issues:
        d = issue_dates.get(n)
        if d and d.get("created"):
            dates.append(d["created"])
        if d and d.get("state", "").upper() == "OPEN":
            any_open = True

    if not dates:
        return None

    first = min(dates)
    last = max(dates)
    return {
        "first_seen_date": first,
        "last_seen_date": last,
        "first_seen_version": date_to_version(first),
        "last_seen_version": date_to_version(last),
        "has_open_evidence": any_open,
    }


def classify_freshness(entity, entity_type):
    """Classify an entity as living, historical, or uncertain."""
    eid = entity["id"]

    # Check manual overrides
    if eid in FRESHNESS_OVERRIDES:
        return FRESHNESS_OVERRIDES[eid]

    temporal = entity.get("temporal", {})
    validation = entity.get("validation", {})

    # Configs confirmed in source are living
    if entity_type == "configs" and validation.get("status") in ("confirmed", "renamed"):
        return ("living", f"Confirmed in source ({validation.get('validated_date', '?')})")

    # No temporal data and no evidence issues = base entity
    if not temporal and not entity.get("evidence_issues"):
        return ("base", "Core ontology entity")

    if not temporal:
        return ("unvalidated", "Has evidence issues but no temporal data")

    last_version = temporal.get("last_seen_version", "")
    has_open = temporal.get("has_open_evidence", False)

    if has_open:
        return ("living", "Has open evidence issue(s)")
    if last_version in ("2.5", "2.6", "2.7"):
        return ("living", f"Last evidence from PT {last_version}")
    if last_version in ("2.3", "2.4"):
        return ("likely_living", f"Last evidence from PT {last_version}")
    if last_version in ("pre-2.0", "2.0", "2.1", "2.2"):
        if entity.get("fix_type") == "diagnostic_technique":
            return ("living", "Diagnostic technique — version-independent")
        return ("historical", f"Last evidence from PT {last_version}")

    return ("uncertain", "Could not determine freshness")


def check_config_in_source(config):
    """Check if a config exists in the current PyTorch source."""
    if not PYTORCH_SOURCE.exists():
        return None, "PyTorch source not found"

    search_names = [config["name"]] + config.get("aliases", [])

    for name in search_names:
        # Skip overly generic names
        if name in ("dynamic", "fullgraph", "verbose"):
            return True, f"{name} (torch.compile kwarg)"

        try:
            result = subprocess.run(
                ["grep", "-rl", "--include=*.py", name,
                 str(PYTORCH_SOURCE / "_dynamo/"),
                 str(PYTORCH_SOURCE / "_inductor/"),
                 str(PYTORCH_SOURCE / "_functorch/")],
                capture_output=True, text=True, timeout=10,
            )
            files = [f for f in result.stdout.strip().split("\n") if f]
            if files:
                short = files[0].replace(str(PYTORCH_SOURCE) + "/", "")
                return True, short
        except subprocess.TimeoutExpired:
            return None, "Search timed out"

    return False, "Not found in source"


def run_validation(args):
    """Main validation logic."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Load corpus dates
    issue_dates = load_corpus_dates()

    summary = {}
    all_results = []

    for entity_type, path in ENTITY_FILES.items():
        if not path.exists():
            print(f"WARNING: {path} not found, skipping", file=sys.stderr)
            continue

        with open(path) as f:
            entities = json.load(f)

        for e in entities:
            # Update temporal data if we have corpus
            if issue_dates and e.get("evidence_issues"):
                temporal = compute_temporal(e["evidence_issues"], issue_dates)
                if temporal:
                    e["temporal"] = temporal

            # Classify freshness
            status, reason = classify_freshness(e, entity_type)

            # Check source for configs
            source_status = None
            if entity_type == "configs" and args.check_source:
                found, location = check_config_in_source(e)
                source_status = {"found": found, "location": location}
                if found is False:
                    status = "stale"
                    reason = f"Not found in current PyTorch source"
                elif found is True:
                    e["validation"] = {
                        "status": "confirmed",
                        "validated_date": today,
                    }

            if args.update:
                e["freshness"] = {
                    "status": status,
                    "reason": reason,
                    "classified_date": today,
                }

            summary[status] = summary.get(status, 0) + 1
            all_results.append({
                "type": entity_type,
                "id": e["id"],
                "name": e.get("name", e["id"]),
                "status": status,
                "reason": reason,
                "source": source_status,
            })

        if args.update:
            with open(path, "w") as f:
                json.dump(entities, f, indent=2)

    # Output
    if args.stats:
        print("=== FRESHNESS SUMMARY ===")
        total = sum(summary.values())
        for status in ["living", "likely_living", "base", "historical", "stale", "uncertain", "unvalidated"]:
            count = summary.get(status, 0)
            if count > 0:
                pct = count / total * 100
                print(f"  {status:15s}: {count:3d} ({pct:.0f}%)")
        print(f"  {'TOTAL':15s}: {total:3d}")
        return

    if args.stale_only:
        stale = [r for r in all_results if r["status"] in ("historical", "stale", "uncertain")]
        if not stale:
            print("All entities are living or base. No staleness concerns.")
            return
        print(f"=== {len(stale)} ENTITIES NEED ATTENTION ===\n")
        for r in stale:
            print(f"[{r['status'].upper()}] [{r['type']}] {r['id']}")
            print(f"  {r['reason']}")
            if r.get("source"):
                print(f"  Source: {r['source']['location']}")
            print()
        return

    # Full report
    print("=" * 60)
    print(f"PT2 ONTOLOGY VALIDATION REPORT — {today}")
    print("=" * 60)

    for entity_type in ENTITY_FILES:
        type_results = [r for r in all_results if r["type"] == entity_type]
        if not type_results:
            continue

        print(f"\n--- {entity_type.upper()} ({len(type_results)} entities) ---")
        for status_group in ["historical", "stale", "uncertain", "likely_living", "living", "base"]:
            group = [r for r in type_results if r["status"] == status_group]
            if not group:
                continue
            label = {"living": "✓", "likely_living": "~", "base": "·", "historical": "✗", "stale": "✗✗", "uncertain": "?"}
            for r in group:
                icon = label.get(r["status"], " ")
                print(f"  {icon} {r['id']}: {r['reason']}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = sum(summary.values())
    for status in ["living", "likely_living", "base", "historical", "stale", "uncertain", "unvalidated"]:
        count = summary.get(status, 0)
        if count > 0:
            pct = count / total * 100
            print(f"  {status:15s}: {count:3d} ({pct:.0f}%)")
    print(f"  {'TOTAL':15s}: {total:3d}")

    if args.update:
        print(f"\nEntity files updated with freshness classifications.")
    if args.check_source:
        configs_checked = [r for r in all_results if r["type"] == "configs"]
        found = sum(1 for r in configs_checked if r.get("source", {}).get("found") is True)
        missing = sum(1 for r in configs_checked if r.get("source", {}).get("found") is False)
        print(f"\nConfig source check: {found} confirmed, {missing} not found")


def main():
    parser = argparse.ArgumentParser(description="Validate PT2 ontology freshness")
    parser.add_argument("--check-source", action="store_true",
                        help="Grep PyTorch source to verify configs exist")
    parser.add_argument("--update", action="store_true",
                        help="Update freshness classifications in entity files")
    parser.add_argument("--stale-only", action="store_true",
                        help="Only show stale/uncertain entities")
    parser.add_argument("--stats", action="store_true",
                        help="Summary statistics only")
    args = parser.parse_args()
    run_validation(args)


if __name__ == "__main__":
    main()
