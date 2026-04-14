#!/usr/bin/env python3
"""
Issue-PR Linker — extracts resolved_by edges from GitHub issue/comment text.

Parses PR references from closed PT2 issues to build ground-truth
resolved_by relationships for the ontology.

Patterns matched:
  - https://github.com/pytorch/pytorch/pull/12345
  - Fixed by #12345 / Fixes #12345 / Closes #12345
  - pytorch/pytorch#12345 (cross-ref format)

Usage:
    # From pre-fetched JSONL data
    python pr_linker.py --input issue_pr_data.jsonl

    # Direct Presto query (requires presto CLI)
    python pr_linker.py --query

    # Output JSON edges
    python pr_linker.py --input data.jsonl --json
"""

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Regex patterns for PR references
PR_PATTERNS = [
    # Full GitHub URL: pytorch/pytorch/pull/12345
    re.compile(r'github\.com/pytorch/pytorch/pull/(\d+)'),
    # "Fixed by #12345", "Fixes #12345", "Closes #12345"
    re.compile(r'(?:fix(?:ed|es)?|clos(?:ed|es)?)\s+(?:by\s+)?#(\d+)', re.IGNORECASE),
    # Cross-ref: pytorch/pytorch#12345
    re.compile(r'pytorch/pytorch#(\d+)'),
]

# Patterns that indicate high confidence the PR actually fixed the issue
# (vs just being mentioned in discussion)
FIX_SIGNAL_PATTERNS = [
    re.compile(r'fixed\s+(?:by|in|with)\s', re.IGNORECASE),
    re.compile(r'this\s+(?:was|is|has been)\s+fixed', re.IGNORECASE),
    re.compile(r'fix(?:es|ed)?\s+#', re.IGNORECASE),
    re.compile(r'clos(?:es|ed)?\s+#', re.IGNORECASE),
    re.compile(r'merged.*fix', re.IGNORECASE),
    re.compile(r'fix.*merged', re.IGNORECASE),
    re.compile(r'is\s+merged\s+and\s+the\s+(?:failure|issue|bug)\s+is\s+fixed', re.IGNORECASE),
]

# Patterns that suggest mention, not fix (lower confidence)
MENTION_PATTERNS = [
    re.compile(r'(?:attempt|trying|started|wip|draft|broke)', re.IGNORECASE),
    re.compile(r'(?:doesn\'t|does not|didn\'t)\s+(?:fix|work|help)', re.IGNORECASE),
    re.compile(r'but\s+it\s+(?:has|didn)', re.IGNORECASE),
]


def extract_pr_numbers(text):
    """Extract unique PR numbers from text."""
    prs = set()
    for pattern in PR_PATTERNS:
        for match in pattern.finditer(text):
            pr_num = int(match.group(1))
            # Filter out issue numbers that are clearly not PRs
            # (very low numbers are unlikely to be PT2-era PRs)
            if pr_num > 10000:
                prs.add(pr_num)
    return prs


def classify_confidence(text, pr_num):
    """Classify confidence that a PR reference is actually a fix.

    Returns: 'high', 'medium', or 'low'
    """
    # Check for explicit fix signals near the PR mention
    pr_str = str(pr_num)

    # Find the PR mention position
    mention_positions = []
    for pattern in PR_PATTERNS:
        for match in pattern.finditer(text):
            if int(match.group(1)) == pr_num:
                mention_positions.append(match.start())

    if not mention_positions:
        return 'low'

    for pos in mention_positions:
        # Look at ~200 chars around the mention
        context = text[max(0, pos - 200):pos + 200].lower()

        # Check for high-confidence fix signals
        for fp in FIX_SIGNAL_PATTERNS:
            if fp.search(context):
                return 'high'

    # Check for negative signals
    for pos in mention_positions:
        context = text[max(0, pos - 200):pos + 200].lower()
        for mp in MENTION_PATTERNS:
            if mp.search(context):
                return 'low'

    # Default: mentioned but not clearly a fix
    return 'medium'


def query_presto():
    """Run Presto query to get issue+comment data with PR references."""
    # Query closed PT2 issues with PR references in comments
    query = """
    SELECT
        CAST(c.issue_number AS BIGINT) AS issue_id,
        i.title,
        i.labels,
        i.closed_at,
        c.body AS text,
        'comment' AS source
    FROM aml.pytorch_github_issue_comments c
    JOIN aml.pytorch_github_issues_metadata i
      ON CAST(i.number AS VARCHAR) = c.issue_number
    WHERE c.ds = (SELECT MAX(ds) FROM aml.pytorch_github_issue_comments)
      AND i.ds = (SELECT MAX(ds) FROM aml.pytorch_github_issues_metadata)
      AND i.labels LIKE '%oncall: pt2%'
      AND i.state = 'closed'
      AND (
        c.body LIKE '%/pull/%'
        OR LOWER(c.body) LIKE '%fixes #%'
        OR LOWER(c.body) LIKE '%closes #%'
        OR LOWER(c.body) LIKE '%fixed by%'
      )
    """
    cmd = ["presto", "aml", "--execute", query, "--output-format", "JSON"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"Presto error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            rows.append(json.loads(line))

    # Also query issue bodies
    body_query = """
    SELECT
        i.number AS issue_id,
        i.title,
        i.labels,
        i.closed_at,
        i.body AS text,
        'body' AS source
    FROM aml.pytorch_github_issues_metadata i
    WHERE i.ds = (SELECT MAX(ds) FROM aml.pytorch_github_issues_metadata)
      AND i.labels LIKE '%oncall: pt2%'
      AND i.state = 'closed'
      AND (
        i.body LIKE '%/pull/%'
        OR LOWER(i.body) LIKE '%fixes #%'
        OR LOWER(i.body) LIKE '%closes #%'
        OR LOWER(i.body) LIKE '%fixed by%'
      )
    """
    cmd2 = ["presto", "aml", "--execute", body_query, "--output-format", "JSON"]
    result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
    if result2.returncode == 0:
        for line in result2.stdout.strip().split("\n"):
            if line.strip():
                rows.append(json.loads(line))

    return rows


def process_rows(rows):
    """Process rows and extract PR linkages."""
    # Group by issue_id
    issue_prs = defaultdict(lambda: {
        "title": "",
        "labels": "",
        "closed_at": "",
        "prs": {},  # pr_num -> {confidence, sources}
    })

    for row in rows:
        issue_id = int(row["issue_id"])
        text = row.get("text", "") or ""
        source = row.get("source", "unknown")

        issue_prs[issue_id]["title"] = row.get("title", "")
        issue_prs[issue_id]["labels"] = row.get("labels", "")
        issue_prs[issue_id]["closed_at"] = row.get("closed_at", "")

        prs = extract_pr_numbers(text)
        for pr_num in prs:
            confidence = classify_confidence(text, pr_num)
            existing = issue_prs[issue_id]["prs"].get(pr_num)
            if existing:
                # Upgrade confidence if we find stronger signal
                conf_rank = {'high': 3, 'medium': 2, 'low': 1}
                if conf_rank.get(confidence, 0) > conf_rank.get(existing["confidence"], 0):
                    existing["confidence"] = confidence
                existing["sources"].add(source)
            else:
                issue_prs[issue_id]["prs"][pr_num] = {
                    "confidence": confidence,
                    "sources": {source},
                }

    return issue_prs


def build_edges(issue_prs, min_confidence="medium"):
    """Build resolved_by edges from issue-PR pairings."""
    conf_rank = {'high': 3, 'medium': 2, 'low': 1}
    min_rank = conf_rank.get(min_confidence, 2)

    edges = []
    for issue_id, data in sorted(issue_prs.items()):
        for pr_num, pr_data in data["prs"].items():
            if conf_rank.get(pr_data["confidence"], 0) >= min_rank:
                edges.append({
                    "issue_id": issue_id,
                    "issue_title": data["title"],
                    "pr_number": pr_num,
                    "pr_url": f"https://github.com/pytorch/pytorch/pull/{pr_num}",
                    "confidence": pr_data["confidence"],
                    "sources": sorted(pr_data["sources"]),
                    "closed_at": data["closed_at"],
                })

    return edges


def print_report(edges, issue_prs):
    """Print human-readable report."""
    print("=" * 60)
    print("ISSUE-PR PAIRING REPORT")
    print("=" * 60)

    total_issues = len(issue_prs)
    issues_with_prs = sum(1 for d in issue_prs.values() if d["prs"])
    total_edges = len(edges)
    high = sum(1 for e in edges if e["confidence"] == "high")
    medium = sum(1 for e in edges if e["confidence"] == "medium")

    print(f"\nIssues scanned: {total_issues}")
    print(f"Issues with PR links: {issues_with_prs}")
    print(f"Edges (medium+ confidence): {total_edges}")
    print(f"  High confidence: {high}")
    print(f"  Medium confidence: {medium}")

    print(f"\n--- High-confidence resolved_by edges ---")
    for e in edges:
        if e["confidence"] == "high":
            print(f"  #{e['issue_id']} → PR #{e['pr_number']}")
            print(f"    {e['issue_title'][:80]}")
            print(f"    {e['pr_url']}")

    print(f"\n--- Medium-confidence edges ---")
    for e in edges:
        if e["confidence"] == "medium":
            print(f"  #{e['issue_id']} → PR #{e['pr_number']}")
            print(f"    {e['issue_title'][:80]}")

    print()


def main():
    input_path = None
    do_query = False
    output_json = False
    min_confidence = "medium"

    for i, arg in enumerate(sys.argv):
        if arg == "--input" and i + 1 < len(sys.argv):
            input_path = sys.argv[i + 1]
        if arg == "--query":
            do_query = True
        if arg == "--json":
            output_json = True
        if arg == "--min-confidence" and i + 1 < len(sys.argv):
            min_confidence = sys.argv[i + 1]

    if do_query:
        print("Querying Presto for issue-PR data...", file=sys.stderr)
        rows = query_presto()
        print(f"Got {len(rows)} rows with PR references", file=sys.stderr)
    elif input_path:
        rows = []
        with open(input_path) as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        print(f"Loaded {len(rows)} rows from {input_path}", file=sys.stderr)
    else:
        print("Usage: python pr_linker.py --query  OR  --input data.jsonl", file=sys.stderr)
        sys.exit(1)

    issue_prs = process_rows(rows)
    edges = build_edges(issue_prs, min_confidence=min_confidence)

    if output_json:
        print(json.dumps({
            "total_issues_scanned": len(issue_prs),
            "total_edges": len(edges),
            "edges": edges,
        }, indent=2))
    else:
        print_report(edges, issue_prs)


if __name__ == "__main__":
    main()
