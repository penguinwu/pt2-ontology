#!/usr/bin/env python3
"""
Entity freshness scanner — detects stale ontology entities.

Compares ontology entities against recent issue data to find:
1. Entities not referenced in recent issues (stale candidates)
2. Entities with declining reference rates (fading)
3. New concepts in issues that don't match any entity (gaps)

Usage:
    # Scan against a classified issue dataset
    python freshness.py classified.json [--months 6] [--threshold 0]

    # Scan against raw issues (runs label classifier internally)
    python freshness.py issues.json --raw [--months 6]
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ONTOLOGY_DIR = Path(__file__).parent.parent / "ontology"


def load_all_entities():
    """Load all entities from the ontology, grouped by type."""
    entities = {}
    entity_dir = ONTOLOGY_DIR / "entities"
    for f in entity_dir.glob("*.json"):
        entity_type = f.stem
        data = json.load(open(f))
        for e in data:
            e["_type"] = entity_type
            entities[e["id"]] = e
    return entities


def scan_freshness(classified_issues, all_entities, months=6):
    """Scan for stale entities based on classified issue data.

    Returns:
    - referenced: entities seen in the classified issues
    - stale: entities NOT seen (candidates for deprecation review)
    - hit_counts: entity_id -> count of issues referencing it
    """
    hit_counts = defaultdict(int)
    hit_issues = defaultdict(list)

    for issue in classified_issues:
        for comp in issue.get("components", []):
            cid = comp["component_id"]
            hit_counts[cid] += 1
            hit_issues[cid].append(issue.get("issue_id"))

        for plat in issue.get("platforms", []):
            pid = plat["platform_id"]
            hit_counts[pid] += 1
            hit_issues[pid].append(issue.get("issue_id"))

    # Determine which entities are referenced vs stale
    # Only check entity types that SHOULD appear in issues
    checkable_types = {
        "components", "causes", "failure_modes", "symptoms",
        "resolutions", "configs", "platforms", "backends",
    }

    referenced = {}
    stale = {}

    for eid, entity in all_entities.items():
        etype = entity.get("_type", "unknown")
        if etype not in checkable_types:
            continue
        if entity.get("deprecated", False):
            continue
        if entity.get("phase", 1) != 1:
            continue  # Skip phase 2 entities (e.g., Helion)

        if eid in hit_counts:
            referenced[eid] = {
                "name": entity.get("name", eid),
                "type": etype,
                "hit_count": hit_counts[eid],
                "example_issues": hit_issues[eid][:5],
            }
        else:
            stale[eid] = {
                "name": entity.get("name", eid),
                "type": etype,
                "hit_count": 0,
                "note": "Not referenced in scanned issues",
            }

    return referenced, stale, dict(hit_counts)


def detect_label_gaps(raw_issues, label_map):
    """Find GitHub labels in issues that don't map to any component."""
    unmapped_labels = defaultdict(int)

    for issue in raw_issues:
        labels_str = issue.get("labels", "")
        if isinstance(labels_str, str):
            labels = [l.strip() for l in labels_str.split(",")]
        else:
            labels = labels_str

        for label in labels:
            if label.startswith("module:") or label.startswith("oncall:"):
                if label not in label_map:
                    unmapped_labels[label] += 1

    return dict(sorted(unmapped_labels.items(), key=lambda x: -x[1]))


def print_report(referenced, stale, hit_counts, unmapped_labels=None):
    """Print a human-readable freshness report."""
    print("=" * 60)
    print("ENTITY FRESHNESS REPORT")
    print("=" * 60)

    print(f"\nReferenced entities: {len(referenced)}")
    print(f"Stale entities:      {len(stale)}")

    if stale:
        print(f"\n--- Stale Entities (review for deprecation) ---")
        by_type = defaultdict(list)
        for eid, info in stale.items():
            by_type[info["type"]].append((eid, info))
        for etype, entities in sorted(by_type.items()):
            print(f"\n  {etype}:")
            for eid, info in entities:
                print(f"    - {info['name']} ({eid})")

    print(f"\n--- Top Referenced Entities ---")
    sorted_refs = sorted(referenced.items(), key=lambda x: -x[1]["hit_count"])[:20]
    for eid, info in sorted_refs:
        print(f"  {info['hit_count']:4d}  {info['name']:35s}  ({info['type']})")

    if unmapped_labels:
        print(f"\n--- Unmapped Labels (potential new entities) ---")
        for label, count in list(unmapped_labels.items())[:20]:
            print(f"  {count:4d}  {label}")

    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    issues = json.load(open(sys.argv[1]))
    all_entities = load_all_entities()

    raw_mode = "--raw" in sys.argv

    if raw_mode:
        # Run classifier internally
        sys.path.insert(0, str(Path(__file__).parent.parent / "extraction"))
        from label_classifier import build_label_map, classify_dataset
        label_map = build_label_map()
        classified = classify_dataset(issues, label_map)
        unmapped = detect_label_gaps(issues, label_map)
    else:
        classified = issues
        unmapped = None

    referenced, stale, hit_counts = scan_freshness(classified, all_entities)

    if "--json" in sys.argv:
        print(json.dumps({
            "referenced": referenced,
            "stale": stale,
            "hit_counts": hit_counts,
            "unmapped_labels": unmapped,
        }, indent=2))
    else:
        print_report(referenced, stale, hit_counts, unmapped)


if __name__ == "__main__":
    main()
