#!/usr/bin/env python3
"""Generate an audit rubric from the PT2 ontology.

Reads ontology entities and relationships, produces a structured rubric
that Beaver can use as ground truth for the documentation audit.

Usage:
    python tools/generate_rubric.py [--output audit_rubric.json]
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ONTOLOGY_DIR = os.path.join(os.path.dirname(__file__), "..", "ontology")


def load_json(path):
    with open(os.path.join(ONTOLOGY_DIR, path)) as f:
        return json.load(f)


def build_entity_index(entities, key="id"):
    """Index a list of entities by their ID field."""
    return {e[key]: e for e in entities}


def build_edge_index(edges):
    """Index edges by type, from, and to for fast lookup."""
    by_type = defaultdict(list)
    by_from = defaultdict(list)
    by_to = defaultdict(list)
    for e in edges:
        by_type[e["type"]].append(e)
        by_from[e["from"]].append(e)
        by_to[e["to"]].append(e)
    return by_type, by_from, by_to


def get_symptom_workarounds(symptom_id, edges_by_type):
    """Find workarounds that address a symptom."""
    results = []
    for edge in edges_by_type.get("addresses_symptom", []):
        if edge["to"] == symptom_id:
            results.append(edge["from"])
    for edge in edges_by_type.get("fixed_by", []):
        if edge["from"] == symptom_id:
            results.append(edge["to"])
    return list(set(results))


def get_symptom_configs(symptom_id, edges_by_type):
    """Find configs relevant to a symptom."""
    results = []
    for edge in edges_by_type.get("involves_config", []):
        if edge["from"] == symptom_id:
            results.append(edge["to"])
    for edge in edges_by_type.get("uses_config", []):
        if edge["from"] == symptom_id:
            results.append(edge["to"])
    for edge in edges_by_type.get("relevant_to", []):
        if edge["to"] == symptom_id:
            results.append(edge["from"])
    return list(set(results))


def get_subtypes(symptom_id, edges_by_type):
    """Find child symptoms (subtypes) of a symptom."""
    results = []
    for edge in edges_by_type.get("is_subtype_of", []):
        if edge["to"] == symptom_id:
            results.append(edge["from"])
    return results


def generate_coverage_checklist(topic, symptom_count, workaround_count, config_count):
    """Generate a coverage checklist for a topic."""
    items = []
    items.append(f"Explains what {topic['name'].lower()} means and common causes")
    if symptom_count > 1:
        items.append(f"Covers {symptom_count} known symptom variants")
    if topic.get("diagnostic_path"):
        items.append("Provides diagnostic steps to identify the specific issue")
    if topic.get("error_signatures"):
        items.append("Lists error signatures users will see")
    if workaround_count > 0:
        items.append(f"Documents {workaround_count} known workarounds")
    if config_count > 0:
        items.append(f"Lists {config_count} relevant config knobs with defaults and effects")
    return items


def generate_rubric(ontology_version="v0.17.1"):
    # Load data
    symptoms = load_json("entities/symptoms.json")
    workarounds = load_json("entities/user_fix_shortcuts.json")
    configs = load_json("entities/configs.json")
    edges = load_json("relationships/evidence_edges.json")
    triage_tree = load_json("relationships/triage_tree.json")
    triage_paths = load_json("relationships/triage_paths.json")

    # Handle wrapper objects
    entry_points = triage_tree.get("entry_points", triage_tree)
    if isinstance(triage_paths, dict) and "paths" in triage_paths:
        triage_paths = triage_paths["paths"]

    # Build indices
    symptom_idx = build_entity_index(symptoms)
    workaround_idx = build_entity_index(workarounds)
    config_idx = build_entity_index(configs)
    edges_by_type, edges_by_from, edges_by_to = build_edge_index(edges)

    # Track which symptoms are covered by topics
    covered_symptoms = set()

    # Build topics from triage tree entry points
    topics = []
    for ep in entry_points:
        related_symptoms = ep.get("related_symptoms", [])
        related_configs = ep.get("related_configs", [])

        # Expand subtypes for each related symptom
        all_symptoms = []
        for s_id in related_symptoms:
            covered_symptoms.add(s_id)
            symptom_data = symptom_idx.get(s_id)
            subtypes = get_subtypes(s_id, edges_by_type)
            covered_symptoms.update(subtypes)

            entry = {
                "id": s_id,
                "name": symptom_data.get("name", s_id) if symptom_data else s_id,
                "description": symptom_data.get("description", "") if symptom_data else "",
            }
            if subtypes:
                entry["subtypes"] = subtypes
            all_symptoms.append(entry)

        # Collect workarounds across all symptoms in this topic
        all_workarounds = {}
        for s_id in related_symptoms + [
            st for s in related_symptoms for st in get_subtypes(s, edges_by_type)
        ]:
            for w_id in get_symptom_workarounds(s_id, edges_by_type):
                if w_id in workaround_idx and w_id not in all_workarounds:
                    w = workaround_idx[w_id]
                    all_workarounds[w_id] = {
                        "id": w_id,
                        "name": w.get("name", w_id),
                        "description": w.get("description", ""),
                    }

        # Collect configs
        all_configs = {}
        for c_id in related_configs:
            if c_id in config_idx:
                c = config_idx[c_id]
                all_configs[c_id] = {
                    "id": c_id,
                    "description": c.get("description", ""),
                }
        # Also add configs linked to symptoms
        for s_id in related_symptoms:
            for c_id in get_symptom_configs(s_id, edges_by_type):
                if c_id in config_idx and c_id not in all_configs:
                    c = config_idx[c_id]
                    all_configs[c_id] = {
                        "id": c_id,
                        "description": c.get("description", ""),
                    }

        # Extract diagnostic steps
        diag_steps = []
        if ep.get("diagnostic_path"):
            for step in ep["diagnostic_path"]:
                diag_steps.append(step.get("action", ""))

        topic = {
            "id": ep["id"],
            "name": ep["id"].replace("_", " ").title(),
            "component": ep.get("component", "unknown"),
            "error_signatures": ep.get("error_signatures", []),
            "symptoms_to_cover": all_symptoms,
            "workarounds_to_document": list(all_workarounds.values()),
            "configs_to_document": list(all_configs.values()),
            "diagnostic_steps": diag_steps,
        }

        topic["coverage_checklist"] = generate_coverage_checklist(
            topic, len(all_symptoms), len(all_workarounds), len(all_configs)
        )
        topics.append(topic)

    # Find orphan symptoms not covered by any topic
    orphan_symptoms = []
    for s in symptoms:
        if s["id"] not in covered_symptoms:
            orphan_symptoms.append({
                "id": s["id"],
                "name": s.get("name", s["id"]),
                "description": s.get("description", ""),
                "component": s.get("component", "unknown"),
            })

    if orphan_symptoms:
        topics.append({
            "id": "uncategorized",
            "name": "Other / Uncategorized Symptoms",
            "component": "various",
            "error_signatures": [],
            "symptoms_to_cover": orphan_symptoms,
            "workarounds_to_document": [],
            "configs_to_document": [],
            "diagnostic_steps": [],
            "coverage_checklist": [
                f"Covers {len(orphan_symptoms)} symptoms not in main triage categories",
                "Each symptom has at least a brief description and workaround if known",
            ],
        })

    # Build rubric
    rubric = {
        "version": "1.0",
        "generated": datetime.now(timezone.utc).isoformat(),
        "ontology_version": ontology_version,
        "description": "PT2 documentation completeness rubric derived from ontology",
        "topics": topics,
        "summary": {
            "total_topics": len(topics),
            "total_symptoms": len(symptoms),
            "total_workarounds": len(workarounds),
            "total_configs": len(configs),
            "symptoms_in_topics": len(covered_symptoms),
            "orphan_symptoms": len(orphan_symptoms),
        },
    }
    return rubric


def main():
    parser = argparse.ArgumentParser(description="Generate PT2 doc audit rubric")
    parser.add_argument("--output", "-o", default="audit_rubric.json",
                        help="Output file path (default: audit_rubric.json)")
    parser.add_argument("--ontology-version", default="v0.17.1",
                        help="Ontology version tag")
    args = parser.parse_args()

    rubric = generate_rubric(args.ontology_version)

    with open(args.output, "w") as f:
        json.dump(rubric, f, indent=2)

    print(f"Generated rubric: {args.output}")
    print(f"  Topics: {rubric['summary']['total_topics']}")
    print(f"  Symptoms covered: {rubric['summary']['symptoms_in_topics']}/{rubric['summary']['total_symptoms']}")
    print(f"  Orphan symptoms: {rubric['summary']['orphan_symptoms']}")
    print(f"  Workarounds: {rubric['summary']['total_workarounds']}")
    print(f"  Configs: {rubric['summary']['total_configs']}")


if __name__ == "__main__":
    main()
