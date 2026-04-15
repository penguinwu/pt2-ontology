#!/usr/bin/env python3
"""
Phase 2: LLM-assisted deep extraction from rich diagnostic conversations.

Processes issues that Phase 1 classified as "unknown" resolution but have 5+ comments
with substantive diagnostic conversations. Extracts root cause chains, diagnostic
reasoning paths, resolution details, and discovers new ontology entities.

Input:  phase2_candidates.json (issue list) + pytorch-issues-pt2-all.json (raw corpus)
Output: phase2_extractions.json

Usage:
    python extraction/extract_phase2.py                    # Process all candidates
    python extraction/extract_phase2.py --batch 20         # Process first 20
    python extraction/extract_phase2.py --issues 100075,93528  # Specific issues
    python extraction/extract_phase2.py --resume           # Skip already-processed
"""

import json
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
GITHUB_DATA = Path("/home/pengwu/projects/pt2-github-issues/pytorch-issues-pt2-all.json")
CANDIDATES = DATA_DIR / "phase2_candidates.json"
OUTPUT = DATA_DIR / "phase2_extractions.json"


def format_issue_for_extraction(issue):
    """Format a raw GitHub issue into the Phase 2 extraction prompt context."""
    body = issue.get('body', '') or ''
    comments = issue.get('comments', [])
    if isinstance(comments, int):
        comments = []

    author = issue.get('author', {})
    author_login = author.get('login', '') if isinstance(author, dict) else str(author or '')

    labels = issue.get('labels', [])
    if isinstance(labels, list):
        label_names = [l.get('name', l) if isinstance(l, dict) else str(l) for l in labels]
    else:
        label_names = [str(labels)]

    created = issue.get('createdAt', '')
    closed = issue.get('closedAt', '')
    state = issue.get('state', '')
    state_reason = issue.get('stateReason', '')

    # Format comments with attribution
    formatted_comments = []
    for i, c in enumerate(comments, 1):
        c_author = c.get('author', {})
        c_login = c_author.get('login', '') if isinstance(c_author, dict) else ''
        c_body = c.get('body', '') or ''
        c_created = c.get('createdAt', '')
        formatted_comments.append(f"[Comment {i}] @{c_login} ({c_created}):\n{c_body}")

    return {
        'number': issue.get('number', 0),
        'title': issue.get('title', ''),
        'author': author_login,
        'state': state,
        'state_reason': state_reason,
        'labels': label_names,
        'created_at': created,
        'closed_at': closed,
        'body': body,
        'comments': formatted_comments,
        'comment_count': len(comments),
    }


def extract_phase2_manually(formatted):
    """
    Manual Phase 2 extraction — analyze the conversation to extract structured fields.
    This is the function that would be replaced by LLM calls in production.
    For now, it builds the extraction template that an LLM would fill.
    """
    return {
        'issue_number': formatted['number'],
        'title': formatted['title'],
        'state': formatted['state'],
        'state_reason': formatted['state_reason'],
        'comment_count': formatted['comment_count'],
        'formatted_prompt': build_extraction_prompt(formatted),
        'phase2': None,  # To be filled by LLM
        'extracted_at': datetime.now().isoformat(),
    }


def build_extraction_prompt(formatted):
    """Build the LLM extraction prompt for a single issue."""
    comments_text = "\n\n".join(formatted['comments'][:30])  # Cap at 30 comments

    return f"""You are analyzing a PyTorch torch.compile (PT2) GitHub issue to extract structured diagnostic information for a domain ontology.

Issue #{formatted['number']}: {formatted['title']}
Author: @{formatted['author']}
State: {formatted['state']} | State Reason: {formatted['state_reason']}
Labels: {', '.join(formatted['labels'])}
Created: {formatted['created_at']} | Closed: {formatted['closed_at']}

--- Issue Body ---
{formatted['body'][:5000]}

--- Comments ({formatted['comment_count']} total, showing up to 30) ---
{comments_text[:15000]}

---

Extract the following in JSON format:

1. root_cause:
   - component: one of [torchdynamo, torchinductor, aot_autograd, functorch, torch_export, triton, autocast, cuda, python_frontend, unknown]
   - mechanism: what specifically went wrong (free text, 1-2 sentences)
   - trigger: what user code/pattern triggered it (free text)
   - confirmed_by: how root cause was confirmed (minifier, bisect, code reading, experimentation, none)

2. diagnostic_path: array of steps, each with:
   - step: number
   - action: what was tried
   - result: what happened
   - conclusion: what was learned

3. resolution:
   - type: one of [compiler_fix, user_workaround, user_adaptation, expected_behavior, wontfix, stale, duplicate, unresolved]
   - description: what resolved it (free text, 1-2 sentences)
   - fix_prs: array of PR numbers (integers)
   - workaround_configs: array of config settings that work around the issue
   - version_fixed: version or "nightly" or "specific commit" or null
   - user_action_required: boolean

4. new_entities:
   - new_configs: array of config names and descriptions not commonly known
   - new_symptoms: array of symptom patterns not in standard taxonomy
   - new_workarounds: array of workaround techniques
   - new_diagnostic_tools: array of tools/techniques used for diagnosis

5. confidence: "high", "medium", or "low" with brief justification

Return ONLY valid JSON."""


def main():
    batch_size = None
    specific_issues = None
    resume = False

    # Parse args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--batch' and i + 1 < len(args):
            batch_size = int(args[i + 1])
            i += 2
        elif args[i] == '--issues' and i + 1 < len(args):
            specific_issues = [int(x) for x in args[i + 1].split(',')]
            i += 2
        elif args[i] == '--resume':
            resume = True
            i += 1
        else:
            print(f"Unknown arg: {args[i]}", file=sys.stderr)
            sys.exit(1)

    # Load corpus
    print(f"Loading corpus from {GITHUB_DATA}...", file=sys.stderr)
    with open(GITHUB_DATA) as f:
        all_issues = json.load(f)
    corpus_map = {issue['number']: issue for issue in all_issues}
    print(f"Loaded {len(corpus_map)} issues", file=sys.stderr)

    # Determine which issues to process
    if specific_issues:
        target_numbers = specific_issues
    else:
        with open(CANDIDATES) as f:
            candidates = json.load(f)
        # Sort by conversation_length desc (richest first)
        candidates.sort(key=lambda x: x.get('conversation_length', 0), reverse=True)
        target_numbers = [c['issue_number'] for c in candidates]

    # Load existing extractions for resume
    existing = {}
    if resume and OUTPUT.exists():
        with open(OUTPUT) as f:
            for entry in json.load(f):
                existing[entry['issue_number']] = entry
        print(f"Loaded {len(existing)} existing extractions", file=sys.stderr)

    # Filter
    if resume:
        target_numbers = [n for n in target_numbers if n not in existing]

    if batch_size:
        target_numbers = target_numbers[:batch_size]

    print(f"Processing {len(target_numbers)} issues...", file=sys.stderr)

    # Process
    results = list(existing.values())  # Start with existing if resuming
    for num in target_numbers:
        raw = corpus_map.get(num)
        if not raw:
            print(f"  #{num}: NOT FOUND in corpus, skipping", file=sys.stderr)
            continue

        formatted = format_issue_for_extraction(raw)
        extraction = extract_phase2_manually(formatted)
        results.append(extraction)
        print(f"  #{num}: prepared ({formatted['comment_count']} comments)", file=sys.stderr)

    # Save
    results.sort(key=lambda x: x['issue_number'])
    with open(OUTPUT, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} extractions to {OUTPUT}", file=sys.stderr)
    print(f"  New this batch: {len(target_numbers)}", file=sys.stderr)
    print(f"  With phase2 data: {sum(1 for r in results if r.get('phase2'))}", file=sys.stderr)
    print(f"  Awaiting LLM: {sum(1 for r in results if not r.get('phase2'))}", file=sys.stderr)


if __name__ == "__main__":
    main()
