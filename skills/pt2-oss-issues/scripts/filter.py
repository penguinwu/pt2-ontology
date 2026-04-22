#!/usr/bin/env python3
"""
Filter Phase 2 extraction candidates from the full oncall:pt2 issue corpus.

Applies label-based filters (human-curated by oncalls) to select issues that
contain diagnostic conversations about torch.compile on NVIDIA+Linux.

Input:  pytorch-issues-pt2-all.json (full corpus)
        diagnostic_extractions_v2.json (Phase 1 results, for "unknown" resolution filter)
Output: phase2_candidates_refined.json

Filters applied (in order):
  1. Resolution: only Phase 1 "unknown" resolution (bugs heuristics couldn't classify)
  2. Conversation depth: 5+ comments (need substance for Phase 2)
  3. DISABLED test issues: excluded by title prefix
  4. Export: exclude "oncall: export" and related (Phase 2 ontology scope)
  5. Feature requests: exclude "feature", "enhancement", 🚀 body prefix
  6. CI/tests: exclude "module: flaky-tests", "module: ci", "module: tests"
  7. Non-compile domains: exclude "oncall: distributed", "oncall: jit", etc.
  8. Non-NVIDIA platforms: exclude ROCm, Intel, XPU, MPS, macOS, Windows, ARM, CPU Inductor
  9. Meta/process labels: exclude "good first issue", "hackathon", "skipped", etc.
 10. Docs/build: exclude "module: docs", "module: binaries", "module: build"

Usage:
    python filter.py                          # Full pipeline
    python filter.py --stats                  # Show filter stats without saving
    python filter.py --min-comments 7         # Raise comment threshold
    python filter.py --include-export         # Don't filter export issues
    python filter.py --include-cpu-inductor   # Don't filter CPU inductor issues
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
GITHUB_DATA = Path.home() / "projects" / "pt2-github-issues" / "pytorch-issues-pt2-all.json"
PHASE1_DATA = DATA_DIR / "diagnostic_extractions_v2.json"
OUTPUT = DATA_DIR / "phase2_candidates_refined.json"

# ─── EXCLUDE LABEL SETS ───────────────────────────────────────────────────────

EXPORT_LABELS = {
    'oncall: export', 'export-triaged', 'export-triage-review',
}

FEATURE_LABELS = {
    'feature', 'enhancement', 'function request', 'release-feature-request',
}

CI_TEST_LABELS = {
    'module: flaky-tests', 'module: ci', 'module: tests', 'module: testing',
    'aggregate flaky test issue',
}

NON_COMPILE_DOMAIN_LABELS = {
    'oncall: distributed', 'oncall: jit', 'oncall: quantization',
    'oncall: profiler', 'oncall: releng', 'oncall: fx', 'oncall: r2p',
    'module: onnx', 'onnx-needs-info', 'onnx-triaged',
}

PLATFORM_LABELS = {
    # Non-NVIDIA GPU backends
    'module: rocm', 'rocm-skipped-tests', 'rocm',
    'module: xpu', 'module: intel', 'intel',
    'module: mps',
    # Non-Linux OS
    'module: macos', 'module: m1', 'module: windows', 'module: wsl',
    # Other architectures
    'module: arm', 'module: POWER',
    # CPU-specific inductor (separate backend)
    'oncall: cpu inductor',
}

META_PROCESS_LABELS = {
    'skipped', 'bot-triaged', 'bot-mislabeled',
    'good first issue', 'hackathon', 'small',
    'module: bootcamp',
}

DOCS_BUILD_LABELS = {
    'module: docs', 'module: binaries', 'module: build', 'module: docker',
    'compile-docs',
}

# Platform keywords for title-based fallback
PLATFORM_TITLE_KEYWORDS = [
    'rocm', 'amd', 'intel', 'xpu', 'mps', 'metal',
    'windows', 'macos', 'mac os', 'apple',
]


def get_labels(issue):
    """Extract label name set from a raw GitHub issue."""
    labels = issue.get('labels', [])
    if isinstance(labels, list):
        return {l.get('name', l) if isinstance(l, dict) else str(l) for l in labels}
    return set()


def has_feature_body(issue):
    """Check if issue body starts with 🚀 (feature request template)."""
    body = issue.get('body', '') or ''
    return body.strip().startswith('### 🚀')


def has_platform_title(issue):
    """Check if title mentions non-NVIDIA/non-Linux platforms."""
    title = issue.get('title', '') or ''
    return any(re.search(kw, title, re.I) for kw in PLATFORM_TITLE_KEYWORDS)


def main():
    # Parse args
    stats_only = '--stats' in sys.argv
    min_comments = 5
    include_export = '--include-export' in sys.argv
    include_cpu_inductor = '--include-cpu-inductor' in sys.argv

    for i, arg in enumerate(sys.argv):
        if arg == '--min-comments' and i + 1 < len(sys.argv):
            min_comments = int(sys.argv[i + 1])

    # Load data
    print("Loading corpus...", file=sys.stderr)
    with open(GITHUB_DATA) as f:
        corpus = json.load(f)
    corpus_map = {issue['number']: issue for issue in corpus}

    print("Loading Phase 1 extractions...", file=sys.stderr)
    with open(PHASE1_DATA) as f:
        phase1 = json.load(f)
    phase1_map = {r['issue_number']: r for r in phase1}

    # ─── FILTER PIPELINE ──────────────────────────────────────────────────

    # Start with Phase 1 "unknown" resolution issues
    unknown_issues = [
        r for r in phase1
        if r['resolution_type'] == 'unknown'
    ]

    filters = []
    current = {r['issue_number'] for r in unknown_issues}
    filters.append(('Phase 1 "unknown" resolution', len(current)))

    # Min comments
    current = {
        n for n in current
        if phase1_map[n].get('conversation_length', 0) >= min_comments
    }
    filters.append((f'{min_comments}+ comments', len(current)))

    # DISABLED test issues (already filtered in Phase 1, but double-check)
    current = {
        n for n in current
        if not (corpus_map.get(n, {}).get('title', '') or '').startswith('DISABLED ')
    }
    filters.append(('Exclude DISABLED tests', len(current)))

    # Build exclude label set based on flags
    exclude_labels = set()
    exclude_labels |= CI_TEST_LABELS
    exclude_labels |= FEATURE_LABELS
    exclude_labels |= NON_COMPILE_DOMAIN_LABELS
    exclude_labels |= META_PROCESS_LABELS
    exclude_labels |= DOCS_BUILD_LABELS

    if not include_export:
        exclude_labels |= EXPORT_LABELS

    if not include_cpu_inductor:
        exclude_labels |= PLATFORM_LABELS
    else:
        exclude_labels |= (PLATFORM_LABELS - {'oncall: cpu inductor'})

    # Apply label exclusions
    label_removed = Counter()
    label_excluded = set()
    for n in current:
        issue = corpus_map.get(n, {})
        labels = get_labels(issue)
        matched = labels & exclude_labels
        if matched:
            label_excluded.add(n)
            for l in matched:
                label_removed[l] += 1

    current -= label_excluded
    filters.append(('Label-based exclusions', len(current)))

    # Feature request body (🚀 prefix not caught by label)
    feature_body = set()
    for n in current:
        issue = corpus_map.get(n, {})
        if has_feature_body(issue):
            feature_body.add(n)
    current -= feature_body
    filters.append(('Feature request body (🚀)', len(current)))

    # Platform title fallback
    platform_title = set()
    for n in current:
        issue = corpus_map.get(n, {})
        if has_platform_title(issue):
            platform_title.add(n)
    current -= platform_title
    filters.append(('Platform title keywords', len(current)))

    # ─── REPORT ───────────────────────────────────────────────────────────

    print(f"\n{'='*60}")
    print(f"PHASE 2 CANDIDATE FILTERING PIPELINE")
    print(f"{'='*60}")
    print(f"Full corpus: {len(corpus)} issues")
    print(f"Phase 1 processed: {len(phase1)} issues\n")

    prev = len(corpus)
    for name, remaining in filters:
        removed = prev - remaining
        print(f"  {name:40s}  -{removed:4d}  → {remaining:4d} remaining")
        prev = remaining

    print(f"\n  {'FINAL CANDIDATES':40s}         {len(current):4d}")

    if label_removed:
        print(f"\n--- Label exclusion breakdown ---")
        for label, count in label_removed.most_common(20):
            print(f"  {count:4d}  {label}")

    if feature_body:
        print(f"\n--- Feature body (🚀) ---")
        print(f"  {len(feature_body)} issues")

    if platform_title:
        print(f"\n--- Platform title fallback ---")
        for n in platform_title:
            title = corpus_map[n].get('title', '')[:70]
            print(f"  #{n}: {title}")

    # ─── BUILD OUTPUT ─────────────────────────────────────────────────────

    candidates = []
    for n in sorted(current):
        p1 = phase1_map[n]
        issue = corpus_map.get(n, {})
        candidates.append({
            'issue_number': n,
            'title': p1.get('title', ''),
            'conversation_length': p1.get('conversation_length', 0),
            'symptoms': [s['type'] for s in p1.get('symptoms', [])],
            'state': p1.get('state', ''),
            'state_reason': p1.get('state_reason', ''),
            'labels': sorted(get_labels(issue) - {'oncall: pt2', 'triaged'}),
        })

    # Priority sort: closed+completed first, then by conversation length
    def priority_key(c):
        is_completed = 1 if (c['state'] == 'closed' and c.get('state_reason') == 'COMPLETED') else 0
        return (-is_completed, -c['conversation_length'])

    candidates.sort(key=priority_key)

    # Stats
    completed = sum(1 for c in candidates if c['state'] == 'closed' and c.get('state_reason') == 'COMPLETED')
    still_open = sum(1 for c in candidates if c['state'] == 'open')
    print(f"\n--- Priority breakdown ---")
    print(f"  Priority A (closed+completed): {completed}")
    print(f"  Priority B (open): {still_open}")
    print(f"  Priority C (other closed): {len(candidates) - completed - still_open}")

    # Conversation length distribution
    lengths = [c['conversation_length'] for c in candidates]
    if lengths:
        print(f"\n--- Conversation length ---")
        print(f"  5-6 comments:  {sum(1 for l in lengths if l in (5,6))}")
        print(f"  7-9 comments:  {sum(1 for l in lengths if 7 <= l <= 9)}")
        print(f"  10-14 comments: {sum(1 for l in lengths if 10 <= l <= 14)}")
        print(f"  15+ comments:  {sum(1 for l in lengths if l >= 15)}")

    if not stats_only:
        with open(OUTPUT, 'w') as f:
            json.dump(candidates, f, indent=2)
        print(f"\nSaved to {OUTPUT}")

    print()


if __name__ == "__main__":
    main()
