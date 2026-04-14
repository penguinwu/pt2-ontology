#!/usr/bin/env python3
"""
Download all oncall:pt2 issues and comments from Hive into local JSONL files.

Produces:
  data/pt2_issues_closed.jsonl   — all closed oncall:pt2 issues with full body
  data/pt2_issues_open.jsonl     — all open oncall:pt2 issues with full body
  data/pt2_comments.jsonl        — all comments for oncall:pt2 issues

Usage:
    python data/download_issues.py
"""

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent
ISSUES_DS = "2026-04-14"
COMMENTS_DS = "2026-03-12"  # Latest available partition


def run_presto(query, timeout=600):
    """Run a Presto query and return rows as list of dicts."""
    result = subprocess.run(
        ["presto", "aml", "--execute", query, "--output-format", "CSV_HEADER"],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        # Filter out the "Connecting to..." and "Running..." lines from stderr
        err_lines = [l for l in result.stderr.strip().split('\n')
                     if not l.startswith('Connecting') and not l.startswith('Running')]
        if err_lines:
            print(f"Presto error: {chr(10).join(err_lines)}", file=sys.stderr)
            return []

    if not result.stdout.strip():
        return []

    reader = csv.DictReader(io.StringIO(result.stdout))
    return list(reader)


def download_issues(state, output_file):
    """Download all oncall:pt2 issues for a given state."""
    print(f"Downloading {state} issues...")
    query = f"""
    SELECT issue_id, number, title, author, state, labels, comment_count,
           created_at, closed_at, updated_at, body, milestone
    FROM pytorch_github_issues_metadata
    WHERE ds = '{ISSUES_DS}'
      AND labels LIKE '%oncall: pt2%'
      AND state = '{state}'
    ORDER BY CAST(number AS BIGINT) DESC
    """
    rows = run_presto(query)
    print(f"  Got {len(rows)} {state} issues")

    with open(output_file, 'w') as f:
        for row in rows:
            # Convert comment_count to int
            if row.get('comment_count'):
                row['comment_count'] = int(row['comment_count'])
            if row.get('issue_id'):
                row['issue_id'] = int(row['issue_id'])
            if row.get('number'):
                row['number'] = int(row['number'])
            f.write(json.dumps(row) + '\n')

    return len(rows)


def download_comments(issue_numbers, output_file):
    """Download comments for given issues in batches."""
    print(f"Downloading comments for {len(issue_numbers)} issues...")
    batch_size = 500
    total = 0

    with open(output_file, 'w') as f:
        for i in range(0, len(issue_numbers), batch_size):
            batch = issue_numbers[i:i + batch_size]
            nums = ",".join(f"'{n}'" for n in batch)
            query = f"""
            SELECT comment_id, issue_id, issue_number, author,
                   created_at_timestamp, updated_at_timestamp, body
            FROM pytorch_github_issue_comments
            WHERE ds = '{COMMENTS_DS}'
              AND issue_number IN ({nums})
            ORDER BY CAST(issue_number AS BIGINT), created_at_timestamp
            """
            rows = run_presto(query, timeout=900)
            for row in rows:
                f.write(json.dumps(row) + '\n')
            total += len(rows)
            print(f"  Batch {i // batch_size + 1}: {len(rows)} comments (total: {total})")

    return total


def main():
    # Download closed issues
    n_closed = download_issues("closed", DATA_DIR / "pt2_issues_closed.jsonl")

    # Download open issues
    n_open = download_issues("open", DATA_DIR / "pt2_issues_open.jsonl")

    # Collect all issue numbers for comment download
    all_numbers = set()
    for fname in ["pt2_issues_closed.jsonl", "pt2_issues_open.jsonl"]:
        path = DATA_DIR / fname
        if path.exists():
            with open(path) as f:
                for line in f:
                    d = json.loads(line)
                    all_numbers.add(str(d['number']))

    # Download comments
    n_comments = download_comments(sorted(all_numbers), DATA_DIR / "pt2_comments.jsonl")

    print(f"\n{'='*50}")
    print(f"Download complete:")
    print(f"  Closed issues: {n_closed}")
    print(f"  Open issues:   {n_open}")
    print(f"  Comments:      {n_comments}")
    print(f"  Comments ds:   {COMMENTS_DS} (latest available)")
    print(f"\nFiles:")
    print(f"  {DATA_DIR / 'pt2_issues_closed.jsonl'}")
    print(f"  {DATA_DIR / 'pt2_issues_open.jsonl'}")
    print(f"  {DATA_DIR / 'pt2_comments.jsonl'}")


if __name__ == "__main__":
    main()
