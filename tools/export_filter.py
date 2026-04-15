#!/usr/bin/env python3
"""
Export filter for the PT2 ontology.

Produces an OSS-safe subset of the ontology by stripping all entities and
relationships tagged as 'internal' or 'confidential'.

Usage:
    python tools/export_filter.py [--level oss] [--output-dir /path/to/output]

The default level is 'oss', which includes only publicly-safe content.
Use '--level internal' to include internal-only content (for Meta-internal use).
"""

import argparse
import json
import os
import sys
from pathlib import Path

VISIBILITY_ORDER = {'oss': 0, 'internal': 1, 'confidential': 2}

ENTITY_FILES = [
    'ontology/entities/symptoms.json',
    'ontology/entities/user_fix_shortcuts.json',
    'ontology/entities/configs.json',
]

RELATIONSHIP_FILES = [
    'ontology/relationships/evidence_edges.json',
    'ontology/relationships/triage_paths.json',
    'ontology/relationships/causal_chains.json',
    'ontology/relationships/resolution_map.json',
    'ontology/relationships/component_playbooks.json',
]

TREE_FILE = 'ontology/relationships/triage_tree.json'


def filter_entities(entities, max_level):
    """Keep only entities at or below the max visibility level."""
    max_ord = VISIBILITY_ORDER.get(max_level, 0)
    return [
        e for e in entities
        if VISIBILITY_ORDER.get(e.get('visibility', 'oss'), 0) <= max_ord
    ]


def filter_edges(edges, allowed_ids, max_level):
    """Keep only edges where both endpoints are in allowed_ids and visibility is OK."""
    max_ord = VISIBILITY_ORDER.get(max_level, 0)
    # Components are always allowed (they're structural, not entities)
    components = {
        'torchdynamo', 'torchinductor', 'aot_autograd', 'torch_export',
        'ddpoptimizer', 'triton', 'torch._dynamo', 'user_error',
    }

    filtered = []
    for e in edges:
        vis_ord = VISIBILITY_ORDER.get(e.get('visibility', 'oss'), 0)
        if vis_ord > max_ord:
            continue

        frm = e.get('from', '')
        to = e.get('to', '')

        frm_ok = frm in allowed_ids or frm in components
        # Allow resolution types, PR URLs, and generic fix categories as targets
        to_ok = (to in allowed_ids or to in components or
                 e.get('type') in ('resolution_type', 'fixed_by_pr') or
                 to in ('compiler_fix', 'upstream_fix', 'user_workaround',
                        'not_a_bug', 'duplicate', 'stale', 'wontfix',
                        'version_upgrade', 'config_change', 'code_rewrite',
                        'op_replacement', 'skip_compile'))

        if frm_ok and to_ok:
            filtered.append(e)

    return filtered


def filter_triage_tree(tree, allowed_ids, max_level):
    """Filter triage tree entry points."""
    max_ord = VISIBILITY_ORDER.get(max_level, 0)

    filtered_entries = []
    for ep in tree.get('entry_points', []):
        vis_ord = VISIBILITY_ORDER.get(ep.get('visibility', 'oss'), 0)
        if vis_ord > max_ord:
            continue

        # Filter referenced entities within entry points
        ep_copy = dict(ep)
        ep_copy['common_fixes'] = [f for f in ep.get('common_fixes', []) if f in allowed_ids]
        ep_copy['related_symptoms'] = [s for s in ep.get('related_symptoms', []) if s in allowed_ids]
        ep_copy['related_configs'] = [c for c in ep.get('related_configs', []) if c in allowed_ids]
        filtered_entries.append(ep_copy)

    result = dict(tree)
    result['entry_points'] = filtered_entries
    return result


def main():
    parser = argparse.ArgumentParser(description='Export filtered ontology')
    parser.add_argument('--level', default='oss', choices=['oss', 'internal'],
                        help='Maximum visibility level to include (default: oss)')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: ontology_export_<level>/)')
    parser.add_argument('--repo-root', default=None,
                        help='Repository root (default: auto-detect)')
    args = parser.parse_args()

    # Find repo root
    if args.repo_root:
        repo_root = Path(args.repo_root)
    else:
        repo_root = Path(__file__).parent.parent

    output_dir = Path(args.output_dir) if args.output_dir else repo_root / f'ontology_export_{args.level}'

    # Load all entities and collect allowed IDs
    allowed_ids = set()
    entity_data = {}

    for relpath in ENTITY_FILES:
        filepath = repo_root / relpath
        with open(filepath) as f:
            entities = json.load(f)

        filtered = filter_entities(entities, args.level)
        for e in filtered:
            allowed_ids.add(e['id'])

        entity_data[relpath] = filtered

    print(f"Entities passing filter (level={args.level}): {len(allowed_ids)}")

    # Filter and write entity files
    os.makedirs(output_dir / 'ontology' / 'entities', exist_ok=True)
    os.makedirs(output_dir / 'ontology' / 'relationships', exist_ok=True)

    for relpath, entities in entity_data.items():
        outpath = output_dir / relpath
        with open(outpath, 'w') as f:
            json.dump(entities, f, indent=2)
        print(f"  {relpath}: {len(entities)} entities")

    # Filter and write relationship files
    for relpath in RELATIONSHIP_FILES:
        filepath = repo_root / relpath
        with open(filepath) as f:
            data = json.load(f)

        if relpath.endswith('triage_paths.json'):
            # Filter triage paths by symptom ID
            filtered = [p for p in data if p.get('symptom') in allowed_ids
                        and VISIBILITY_ORDER.get(p.get('visibility', 'oss'), 0)
                        <= VISIBILITY_ORDER.get(args.level, 0)]
            # Also filter referenced entities within paths
            for p in filtered:
                p['workarounds'] = [w for w in p.get('workarounds', []) if w in allowed_ids]
                p['configs'] = [c for c in p.get('configs', []) if c in allowed_ids]
        elif relpath.endswith('component_playbooks.json'):
            filtered = [pb for pb in data
                        if VISIBILITY_ORDER.get(pb.get('visibility', 'oss'), 0)
                        <= VISIBILITY_ORDER.get(args.level, 0)]
            for pb in filtered:
                pb['symptoms'] = [s for s in pb.get('symptoms', []) if s in allowed_ids]
                pb['workarounds'] = [w for w in pb.get('workarounds', []) if w in allowed_ids]
                pb['configs'] = [c for c in pb.get('configs', []) if c in allowed_ids]
        else:
            filtered = filter_edges(data, allowed_ids, args.level)

        outpath = output_dir / relpath
        with open(outpath, 'w') as f:
            json.dump(filtered, f, indent=2)
        print(f"  {relpath}: {len(filtered)} items")

    # Filter and write triage tree
    filepath = repo_root / TREE_FILE
    with open(filepath) as f:
        tree = json.load(f)

    filtered_tree = filter_triage_tree(tree, allowed_ids, args.level)
    outpath = output_dir / TREE_FILE
    with open(outpath, 'w') as f:
        json.dump(filtered_tree, f, indent=2)
    print(f"  {TREE_FILE}: {len(filtered_tree['entry_points'])} entry points")

    # Validate: check for dangling references
    print(f"\nExport complete: {output_dir}")
    print(f"Total entities: {len(allowed_ids)}")


if __name__ == '__main__':
    main()
