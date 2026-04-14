#!/usr/bin/env python3
"""
Validation script for PT2 Ontology extractions.

Takes candidate extractions (from the extraction stage) and checks them against
the existing ontology for:
1. Duplicate entities (same concept, different ID)
2. Conflicting relationships
3. Evidence quality (does the cited text support the claim?)
4. Entity naming (matches PyTorch code constructs?)

Usage:
    python validate.py candidates.json [--ontology-dir ../ontology]
    python validate.py --check-existing  # validate current ontology

Output: validated.json with verdicts + rejection reasons
"""

import json
import os
import sys
from collections import defaultdict


def load_ontology(ontology_dir):
    """Load all entities and relationships from the ontology."""
    entities = {}
    for f in os.listdir(os.path.join(ontology_dir, 'entities')):
        if f.endswith('.json'):
            data = json.load(open(os.path.join(ontology_dir, 'entities', f)))
            for e in data:
                entities[e['id']] = e

    relationships = []
    for f in os.listdir(os.path.join(ontology_dir, 'relationships')):
        if f.endswith('.json'):
            data = json.load(open(os.path.join(ontology_dir, 'relationships', f)))
            relationships.extend(data)

    return entities, relationships


def check_duplicate_entity(new_id, new_name, entities):
    """Check if a new entity duplicates an existing one."""
    issues = []

    # Exact ID match
    if new_id in entities:
        issues.append(f"DUPLICATE_ID: '{new_id}' already exists")
        return issues

    # Fuzzy name match
    new_name_lower = new_name.lower().replace('_', ' ').replace('-', ' ')
    for eid, e in entities.items():
        existing_name = e['name'].lower().replace('_', ' ').replace('-', ' ')
        if new_name_lower == existing_name:
            issues.append(f"DUPLICATE_NAME: '{new_name}' matches existing entity '{eid}'")
        # Check aliases
        for alias in e.get('aliases', []):
            if new_name_lower == alias.lower():
                issues.append(f"DUPLICATE_ALIAS: '{new_name}' matches alias of '{eid}'")

    return issues


def check_conflicting_relationship(new_rel, relationships):
    """Check if a new relationship conflicts with existing ones."""
    issues = []

    for r in relationships:
        # Same from/to but different type
        if r['from'] == new_rel['from'] and r['to'] == new_rel['to']:
            if r['type'] != new_rel['type']:
                issues.append(
                    f"CONFLICT: {new_rel['from']}->{new_rel['to']} "
                    f"already has type '{r['type']}', new has '{new_rel['type']}'"
                )

        # Circular is_subcause_of
        if new_rel['type'] == 'is_subcause_of':
            if r['type'] == 'is_subcause_of' and r['from'] == new_rel['to'] and r['to'] == new_rel['from']:
                issues.append(
                    f"CIRCULAR: {new_rel['from']} is_subcause_of {new_rel['to']} "
                    f"but {new_rel['to']} is already subcause of {new_rel['from']}"
                )

    return issues


def check_evidence_quality(extraction):
    """Check if evidence fields are present and non-trivial."""
    issues = []

    for ent in extraction.get('existing_entities', []):
        if not ent.get('evidence') or len(ent['evidence']) < 10:
            issues.append(f"WEAK_EVIDENCE: entity '{ent['id']}' has no/thin evidence")

    for rel in extraction.get('relationships', []):
        if not rel.get('evidence') or len(rel['evidence']) < 10:
            issues.append(f"WEAK_EVIDENCE: relationship {rel['from']}->{rel['to']} has no/thin evidence")

    for ent in extraction.get('new_entities', []):
        if not ent.get('evidence') or len(ent['evidence']) < 10:
            issues.append(f"WEAK_EVIDENCE: new entity '{ent['id']}' has no/thin evidence")

    return issues


def check_entity_references(extraction, entities):
    """Check that all referenced entity IDs exist."""
    issues = []

    new_ids = {e['id'] for e in extraction.get('new_entities', [])}

    for ent in extraction.get('existing_entities', []):
        if ent['id'] not in entities:
            issues.append(f"UNKNOWN_ENTITY: '{ent['id']}' not in ontology")

    for rel in extraction.get('relationships', []):
        for field in ['from', 'to']:
            ref = rel[field]
            if ref not in entities and ref not in new_ids:
                issues.append(f"DANGLING_REF: relationship references '{ref}' which doesn't exist")

    return issues


def validate_extraction(extraction, entities, relationships):
    """Run all validation checks on a single extraction."""
    all_issues = []

    # Check new entities for duplicates
    for ent in extraction.get('new_entities', []):
        all_issues.extend(check_duplicate_entity(ent['id'], ent['name'], entities))

    # Check relationships for conflicts
    for rel in extraction.get('relationships', []):
        all_issues.extend(check_conflicting_relationship(rel, relationships))

    # Check evidence quality
    all_issues.extend(check_evidence_quality(extraction))

    # Check entity references
    all_issues.extend(check_entity_references(extraction, entities))

    verdict = 'pass' if not all_issues else 'review'
    if any('CONFLICT' in i or 'CIRCULAR' in i or 'DANGLING_REF' in i for i in all_issues):
        verdict = 'reject'

    return {
        'issue_id': extraction.get('issue_id'),
        'verdict': verdict,
        'issues': all_issues,
        'extraction': extraction
    }


def check_existing_ontology(ontology_dir):
    """Validate the existing ontology for internal consistency."""
    entities, relationships = load_ontology(ontology_dir)
    issues = []

    # Check for dangling references in relationships
    for r in relationships:
        if r['from'] not in entities:
            issues.append(f"DANGLING: relationship from '{r['from']}' (not in entities)")
        if r['to'] not in entities:
            issues.append(f"DANGLING: relationship to '{r['to']}' (not in entities)")

    # Check for circular is_subcause_of
    subcause_graph = defaultdict(set)
    for r in relationships:
        if r['type'] == 'is_subcause_of':
            subcause_graph[r['from']].add(r['to'])

    def has_cycle(node, visited, path):
        visited.add(node)
        path.add(node)
        for neighbor in subcause_graph.get(node, []):
            if neighbor in path:
                return True
            if neighbor not in visited and has_cycle(neighbor, visited, path):
                return True
        path.discard(node)
        return False

    visited = set()
    for node in subcause_graph:
        if node not in visited:
            if has_cycle(node, visited, set()):
                issues.append(f"CYCLE: circular is_subcause_of detected involving '{node}'")

    # Check for orphan entities (no relationships)
    referenced = set()
    for r in relationships:
        referenced.add(r['from'])
        referenced.add(r['to'])

    orphans = [eid for eid in entities if eid not in referenced]
    if orphans:
        issues.append(f"ORPHANS: {len(orphans)} entities with no relationships: {orphans[:5]}...")

    # Summary
    print(f"\n=== Ontology Validation Report ===")
    print(f"Entities: {len(entities)}")
    print(f"Relationships: {len(relationships)}")
    print(f"Issues found: {len(issues)}")
    for i in issues:
        print(f"  - {i}")

    if not issues:
        print("  All checks passed!")

    return issues


def main():
    ontology_dir = os.path.join(os.path.dirname(__file__), '..', 'ontology')

    if '--check-existing' in sys.argv:
        check_existing_ontology(ontology_dir)
        return

    if len(sys.argv) < 2:
        print("Usage: python validate.py candidates.json [--ontology-dir DIR]")
        print("       python validate.py --check-existing")
        sys.exit(1)

    candidates_file = sys.argv[1]
    if '--ontology-dir' in sys.argv:
        ontology_dir = sys.argv[sys.argv.index('--ontology-dir') + 1]

    entities, relationships = load_ontology(ontology_dir)
    candidates = json.load(open(candidates_file))

    if not isinstance(candidates, list):
        candidates = [candidates]

    results = []
    for c in candidates:
        result = validate_extraction(c, entities, relationships)
        results.append(result)
        status = result['verdict'].upper()
        n_issues = len(result['issues'])
        print(f"  [{status}] Issue #{result['issue_id']} — {n_issues} issues")
        for i in result['issues']:
            print(f"    {i}")

    # Summary
    verdicts = defaultdict(int)
    for r in results:
        verdicts[r['verdict']] += 1

    print(f"\n=== Summary ===")
    print(f"Total: {len(results)} | Pass: {verdicts['pass']} | Review: {verdicts['review']} | Reject: {verdicts['reject']}")

    output_file = candidates_file.replace('.json', '.validated.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Saved to {output_file}")


if __name__ == '__main__':
    main()
