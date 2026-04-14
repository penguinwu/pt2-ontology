#!/usr/bin/env python3
"""
Label-based issue classifier for the PT2 ontology extraction pipeline.

Stage 1 of the pipeline: fast, deterministic classification using
human-validated GitHub labels. Runs before LLM extraction to provide
high-confidence component and metadata tags.

Usage:
    # Classify a single issue dataset
    python label_classifier.py issues.json > classified.json

    # Classify with stats output
    python label_classifier.py issues.json --stats

    # Build the label map from components.json (for inspection)
    python label_classifier.py --dump-map
"""

import json
import sys
import os
from pathlib import Path

ONTOLOGY_DIR = Path(__file__).parent.parent / "ontology"


def build_label_map():
    """Build inverse mapping: GitHub label -> component entities."""
    components = json.load(open(ONTOLOGY_DIR / "entities" / "components.json"))

    label_to_components = {}
    for c in components:
        for label in c.get("github_labels", []):
            if label not in label_to_components:
                label_to_components[label] = []
            label_to_components[label].append({
                "component_id": c["id"],
                "component_name": c["name"],
                "sto": c.get("sto"),
                "sto_scope": c.get("sto_scope"),
            })

    return label_to_components


# Cross-cutting labels: describe bug characteristics, not components
CROSS_CUTTING_LABELS = {
    "module: regression": "regression",
    "module: crash": "crash",
    "module: ci": "ci",
    "high priority": "high_priority",
    "triaged": "triaged",
    "needs reproduction": "needs_repro",
    "pt2: ubn": "ubn",
}

# Platform detection from labels and title keywords
PLATFORM_LABELS = {
    "module: mps": "apple_mps",
    "module: rocm": "amd_gpu",
    "module: xpu": "intel_xpu",
    "module: cpu": "intel_cpu",
}

PLATFORM_TITLE_PATTERNS = {
    "mps": "apple_mps",
    "rocm": "amd_gpu",
    "xpu": "intel_xpu",
    "cpu-only": "intel_cpu",
    "cpu only": "intel_cpu",
    "windows": "windows",
    "win32": "windows",
    "macos": "macos",
    "mac os": "macos",
    "apple silicon": "arm_cpu",
    "arm": "arm_cpu",
    "tpu": "google_tpu",
}


def classify_issue(issue, label_map):
    """Classify a single issue using its labels and title.

    Returns a dict with:
    - components: list of matched components with confidence
    - tags: cross-cutting metadata tags
    - platforms: non-default platforms detected
    - unclassified: True if no component labels matched
    """
    labels_str = issue.get("labels", "")
    # Labels come as comma-separated string from Hive
    if isinstance(labels_str, str):
        labels = [l.strip() for l in labels_str.split(",")]
    else:
        labels = labels_str

    title = issue.get("title", "").lower()

    # Component classification from labels
    components = []
    seen_ids = set()
    for label in labels:
        if label in label_map:
            for comp in label_map[label]:
                if comp["component_id"] not in seen_ids:
                    components.append({
                        "component_id": comp["component_id"],
                        "component_name": comp["component_name"],
                        "sto": comp["sto"],
                        "matched_label": label,
                        "confidence": "high",  # label-based = human-validated
                    })
                    seen_ids.add(comp["component_id"])

    # Cross-cutting tags
    tags = []
    for label in labels:
        if label in CROSS_CUTTING_LABELS:
            tags.append(CROSS_CUTTING_LABELS[label])

    # Platform detection (labels first, then title patterns)
    platforms = []
    seen_platforms = set()
    for label in labels:
        if label in PLATFORM_LABELS:
            pid = PLATFORM_LABELS[label]
            if pid not in seen_platforms:
                platforms.append({"platform_id": pid, "source": "label", "confidence": "high"})
                seen_platforms.add(pid)

    for pattern, pid in PLATFORM_TITLE_PATTERNS.items():
        if pattern in title and pid not in seen_platforms:
            platforms.append({"platform_id": pid, "source": "title", "confidence": "medium"})
            seen_platforms.add(pid)

    return {
        "issue_id": issue.get("issue_id") or issue.get("number"),
        "title": issue.get("title"),
        "components": components,
        "tags": tags,
        "platforms": platforms,
        "unclassified": len(components) == 0,
    }


def classify_dataset(issues, label_map):
    """Classify all issues in a dataset."""
    return [classify_issue(issue, label_map) for issue in issues]


def print_stats(results):
    """Print classification statistics."""
    total = len(results)
    classified = sum(1 for r in results if not r["unclassified"])
    unclassified = total - classified
    with_platform = sum(1 for r in results if r["platforms"])
    with_tags = sum(1 for r in results if r["tags"])
    high_priority = sum(1 for r in results if "high_priority" in r["tags"])

    # Component distribution
    comp_counts = {}
    for r in results:
        for c in r["components"]:
            cid = c["component_id"]
            comp_counts[cid] = comp_counts.get(cid, 0) + 1

    print(f"\n--- Classification Stats ---")
    print(f"Total issues:      {total}")
    print(f"Classified:        {classified} ({classified/total*100:.1f}%)")
    print(f"Unclassified:      {unclassified} ({unclassified/total*100:.1f}%)")
    print(f"With platform tag: {with_platform}")
    print(f"High priority:     {high_priority}")
    print(f"\nComponent distribution:")
    for cid, count in sorted(comp_counts.items(), key=lambda x: -x[1]):
        print(f"  {cid:35s} {count:4d}")

    if unclassified > 0:
        print(f"\nUnclassified issues:")
        for r in results:
            if r["unclassified"]:
                print(f"  #{r['issue_id']}: {r['title']}")


def main():
    if "--dump-map" in sys.argv:
        label_map = build_label_map()
        print(json.dumps(label_map, indent=2))
        return

    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        print(__doc__)
        sys.exit(1)

    issues = json.load(open(sys.argv[1]))
    label_map = build_label_map()
    results = classify_dataset(issues, label_map)

    if "--stats" in sys.argv:
        print_stats(results)
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
