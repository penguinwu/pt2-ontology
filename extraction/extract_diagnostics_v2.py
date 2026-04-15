#!/usr/bin/env python3
"""
Phase 1 v2: Heuristic diagnostic extraction from full GitHub API dataset.

Works with the GitHub API JSON format (camelCase fields, inline comments).
Processes ALL issues (open + closed), not just closed ones from Hive.

Input:  ../data/pytorch-issues-pt2-all.json  (or symlink to pt2-github-issues)
Output: ../data/diagnostic_extractions_v2.json

Usage:
    python extraction/extract_diagnostics_v2.py
    python extraction/extract_diagnostics_v2.py --json       # JSON to stdout
    python extraction/extract_diagnostics_v2.py --stats-only # Summary only
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
GITHUB_DATA = Path("/home/pengwu/projects/pt2-github-issues/pytorch-issues-pt2-all.json")

# --- Resolution Type Classification ---
RESOLUTION_CLASSIFIERS = [
    (re.compile(r'(?:duplicate|dup)\s+(?:of|issue|#)', re.I), 'duplicate'),
    (re.compile(r'closing\s+as\s+(?:a\s+)?dup', re.I), 'duplicate'),
    (re.compile(r'(?:stale|inactive|no\s+activity)', re.I), 'stale'),
    (re.compile(r'pytorch-bot.*closing.*stale', re.I), 'stale'),
    (re.compile(r"(?:won't\s+fix|wontfix|not\s+a\s+bug|by\s+design|expected\s+behavior|working\s+as\s+intended)", re.I), 'wontfix'),
    (re.compile(r"this\s+is\s+(?:expected|intended|correct)\s+behavior", re.I), 'wontfix'),
    (re.compile(r'(?:workaround|work\s+around)\s*(?:is|:|would\s+be|for\s+now)', re.I), 'user_workaround'),
    (re.compile(r'(?:try\s+(?:to\s+)?(?:set(?:ting)?|us(?:e|ing)|switch(?:ing)?|disabl(?:e|ing)))', re.I), 'user_workaround'),
    (re.compile(r'(?:upgrade|update)\s+(?:to|your|pytorch|torch)', re.I), 'user_adaptation'),
    (re.compile(r'(?:fixed|resolved)\s+(?:in|on)\s+(?:nightly|main|latest|2\.\d+)', re.I), 'user_adaptation'),
    (re.compile(r'(?:this|the\s+issue)\s+(?:is|was|has\s+been)\s+fixed\s+in', re.I), 'user_adaptation'),
    (re.compile(r'(?:fixed|resolved|addressed)\s+(?:by|in|via|with)\s+(?:#|https://github\.com/pytorch/pytorch/pull/)\d+', re.I), 'compiler_fix'),
    (re.compile(r'(?:fix|patch|pr|pull\s+request)\s*(?:#|https://github\.com/pytorch/pytorch/pull/)\d+', re.I), 'compiler_fix'),
    (re.compile(r'https://github\.com/pytorch/pytorch/pull/\d+', re.I), 'compiler_fix'),
    (re.compile(r'(?:merged|landed)\s+(?:the\s+)?(?:fix|pr|patch)', re.I), 'compiler_fix'),
]

# --- Symptom Classification ---
SYMPTOM_CLASSIFIERS = [
    (re.compile(r'(?:wrong|incorrect|different|mismatch)\s+(?:result|output|answer|value|shape)', re.I), 'wrong_result'),
    (re.compile(r'(?:silent(?:ly)?)\s+(?:wrong|incorrect|produces|returns)', re.I), 'silent_correctness'),
    (re.compile(r'(?:crash|segfault|SIGSEGV|SIGABRT|core\s+dump|illegal\s+instruction)', re.I), 'crash'),
    (re.compile(r'(?:RuntimeError|TypeError|ValueError|AttributeError|AssertionError|KeyError)', re.I), 'error_raised'),
    (re.compile(r'(?:Traceback|traceback|Exception)', re.I), 'error_raised'),
    (re.compile(r'(?:slow|takes?\s+(?:long|forever|minutes|hours))\s*(?:to\s+)?compil', re.I), 'slow_compile'),
    (re.compile(r'(?:compilation|compile)\s+(?:time|is\s+slow|takes)', re.I), 'slow_compile'),
    (re.compile(r'performance\s+(?:regression|degradation|drop)', re.I), 'perf_regression'),
    (re.compile(r'(?:slower|regression)\s+(?:than|compared|vs)\s+(?:eager|without\s+compile)', re.I), 'perf_regression'),
    (re.compile(r'\b(?:hang(?:s|ing|ed)?|stuck|freeze[sd]?|deadlock(?:ed)?|never\s+(?:finish|return|complete))\b', re.I), 'hang'),
    (re.compile(r'(?:OOM|out\s+of\s+memory|memory\s+(?:leak|error|issue))', re.I), 'memory_issue'),
    (re.compile(r'\b(?:flaky|intermittent|non-deterministic)\b', re.I), 'flaky'),
    (re.compile(r'\bgraph\s*break', re.I), 'graph_break'),
    (re.compile(r'\brecompil(?:ation|ing|e)\b', re.I), 'recompilation'),
]

# --- Workaround Extraction ---
WORKAROUND_PATTERNS = [
    (re.compile(r'(torch\._(?:dynamo|inductor)\.config\.\w+\s*=\s*\S+)', re.I), 'config_toggle'),
    (re.compile(r'(TORCHDYNAMO_\w+\s*=\s*\S+)', re.I), 'env_var'),
    (re.compile(r'(TORCHINDUCTOR_\w+\s*=\s*\S+)', re.I), 'env_var'),
    (re.compile(r'(PYTORCH_CUDA_ALLOC_CONF\s*=\s*\S+)', re.I), 'env_var'),
    (re.compile(r'(?:try|use|switch\s+to|set)\s+.*(?:mode\s*=\s*["\'](\w+)["\'])', re.I), 'mode_change'),
    (re.compile(r'(?:try|use|switch\s+to)\s+.*(?:backend\s*=\s*["\'](\w+)["\'])', re.I), 'backend_switch'),
    (re.compile(r'(?:disable|turn\s+off|remove)\s+(?:torch\.)?compile', re.I), 'disable_compile'),
    (re.compile(r'(?:run|use)\s+(?:in\s+)?eager\s+mode', re.I), 'disable_compile'),
    (re.compile(r'(?:mark_dynamic|torch\._dynamo\.mark_dynamic)', re.I), 'guard_adjustment'),
    (re.compile(r'dynamic\s*=\s*True', re.I), 'guard_adjustment'),
    (re.compile(r'(?:torch\.no_grad|with\s+no_grad|inference_mode)', re.I), 'inference_mode'),
    (re.compile(r'(?:replace|use|try)\s+(?:\w+\s+)?(?:instead\s+of|rather\s+than)', re.I), 'op_replacement'),
]

# --- Diagnostic Tool References ---
DIAGNOSTIC_TOOL_PATTERNS = [
    (re.compile(r'TORCH_LOGS', re.I), 'torch_logs'),
    (re.compile(r'torch\._dynamo\.utils\.(?:repro_after|minify)', re.I), 'minifier'),
    (re.compile(r'minif(?:y|ier|ied|ication)', re.I), 'minifier'),
    (re.compile(r'bisect', re.I), 'bisect'),
    (re.compile(r'torch\.compile.*backend\s*=\s*["\']eager["\']', re.I), 'eager_backend'),
    (re.compile(r'aot_eager', re.I), 'aot_eager_backend'),
    (re.compile(r'TORCH_COMPILE_DEBUG', re.I), 'compile_debug'),
    (re.compile(r'torch\._dynamo\.explain', re.I), 'dynamo_explain'),
    (re.compile(r'graph_dump|print_graph|print_tabular', re.I), 'graph_dump'),
]


def classify_resolution(body_text, comments_text):
    for pattern, rtype in RESOLUTION_CLASSIFIERS:
        if pattern.search(comments_text):
            m = pattern.search(comments_text)
            evidence = comments_text[max(0, m.start()-40):m.end()+80].strip()[:200]
            return rtype, evidence
    for pattern, rtype in RESOLUTION_CLASSIFIERS:
        if pattern.search(body_text):
            m = pattern.search(body_text)
            evidence = body_text[max(0, m.start()-40):m.end()+80].strip()[:200]
            return rtype, evidence
    return 'unknown', ''


def classify_symptoms(text):
    symptoms = []
    seen = set()
    for pattern, stype in SYMPTOM_CLASSIFIERS:
        if pattern.search(text) and stype not in seen:
            seen.add(stype)
            m = pattern.search(text)
            evidence = text[max(0, m.start()-30):m.end()+80].strip()[:150]
            symptoms.append({'type': stype, 'evidence': evidence})
    return symptoms


def extract_workarounds(body_text, comments_text):
    combined = body_text + "\n" + comments_text
    workarounds = []
    seen = set()
    for pattern, wtype in WORKAROUND_PATTERNS:
        for m in pattern.finditer(combined):
            snippet = m.group(0)[:150]
            key = f"{wtype}:{snippet[:50]}"
            if key not in seen:
                seen.add(key)
                context = combined[max(0, m.start()-60):m.end()+100].strip()[:250]
                workarounds.append({'type': wtype, 'snippet': snippet, 'context': context})
    return workarounds


def extract_diagnostic_tools(body_text, comments_text):
    combined = body_text + "\n" + comments_text
    tools = set()
    for pattern, tool in DIAGNOSTIC_TOOL_PATTERNS:
        if pattern.search(combined):
            tools.add(tool)
    return sorted(tools)


def extract_fix_prs(body_text, comments_text):
    combined = body_text + "\n" + comments_text
    pr_fix = re.compile(r'(?:fixed|resolved|addressed|fix|patch)\s+(?:by|in|via|with)\s+(?:https://github\.com/pytorch/pytorch/pull/|#)(\d+)', re.I)
    pr_link = re.compile(r'https://github\.com/pytorch/pytorch/pull/(\d+)')
    prs = set()
    for m in pr_fix.finditer(combined):
        prs.add(int(m.group(1)))
    for m in pr_link.finditer(combined):
        prs.add(int(m.group(1)))
    return sorted(prs)


def extract_labels(issue):
    """Extract label names from GitHub API format."""
    labels = issue.get('labels', [])
    if isinstance(labels, str):
        return [l.strip() for l in labels.split(',') if l.strip()]
    if isinstance(labels, list):
        return [l.get('name', l) if isinstance(l, dict) else str(l) for l in labels]
    return []


def process_issue(issue):
    """Extract diagnostic workflow from a GitHub API issue with inline comments."""
    body = issue.get('body', '') or ''

    # GitHub API format: comments is a list of comment objects
    comments = issue.get('comments', [])
    if isinstance(comments, int):
        comments = []
    comments_text = "\n".join(c.get('body', '') or '' for c in comments)

    # Skip DISABLED test issues
    title = issue.get('title', '')
    if title.startswith('DISABLED '):
        return None

    resolution_type, resolution_evidence = classify_resolution(body, comments_text)
    symptoms = classify_symptoms(body)
    workarounds = extract_workarounds(body, comments_text)
    diagnostic_tools = extract_diagnostic_tools(body, comments_text)
    fix_prs = extract_fix_prs(body, comments_text)

    # Time to resolution
    ttr_days = None
    created = issue.get('createdAt') or issue.get('created_at')
    closed = issue.get('closedAt') or issue.get('closed_at')
    if created and closed:
        try:
            c = datetime.fromisoformat(created.replace('Z', '+00:00'))
            cl = datetime.fromisoformat(closed.replace('Z', '+00:00'))
            ttr_days = (cl - c).days
        except (ValueError, TypeError):
            pass

    # State
    state = issue.get('state', '').lower()
    state_reason = issue.get('stateReason') or issue.get('state_reason')

    # Author
    author = issue.get('author', {})
    if isinstance(author, dict):
        author_login = author.get('login', '')
    else:
        author_login = str(author) if author else ''

    labels = extract_labels(issue)
    comment_count = len(comments) if isinstance(issue.get('comments'), list) else (issue.get('comment_count', 0) or 0)

    return {
        'issue_number': issue.get('number', 0),
        'title': title,
        'state': state,
        'state_reason': state_reason,
        'labels': labels,
        'author': author_login,
        'comment_count': comment_count,
        'resolution_type': resolution_type,
        'resolution_evidence': resolution_evidence,
        'symptoms': symptoms,
        'workarounds': workarounds,
        'diagnostic_tools': diagnostic_tools,
        'fix_prs': fix_prs,
        'time_to_resolution_days': ttr_days,
        'has_conversation': comment_count > 0,
        'conversation_length': comment_count,
    }


def main():
    output_json = '--json' in sys.argv
    stats_only = '--stats-only' in sys.argv

    # Load GitHub API dataset
    print(f"Loading {GITHUB_DATA}...", file=sys.stderr)
    with open(GITHUB_DATA) as f:
        all_issues = json.load(f)
    print(f"Loaded {len(all_issues)} issues", file=sys.stderr)

    results = []
    disabled_count = 0
    for issue in all_issues:
        result = process_issue(issue)
        if result is None:
            disabled_count += 1
            continue
        results.append(result)

    print(f"Processed {len(results)} issues (skipped {disabled_count} DISABLED)", file=sys.stderr)

    # Save results
    output_path = DATA_DIR / "diagnostic_extractions_v2.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Saved to {output_path}", file=sys.stderr)

    if output_json:
        print(json.dumps(results, indent=2))
        return

    # --- Report ---
    closed = [r for r in results if r['state'] == 'closed']
    opened = [r for r in results if r['state'] == 'open']

    print(f"\n{'='*60}")
    print(f"DIAGNOSTIC EXTRACTION v2 — Full GitHub Dataset")
    print(f"{'='*60}")
    print(f"Total issues: {len(results)} ({len(closed)} closed, {len(opened)} open)")
    print(f"Issues with conversations: {sum(1 for r in results if r['has_conversation'])}")
    print(f"Skipped DISABLED: {disabled_count}")

    # Resolution type distribution (closed only)
    res_counts = defaultdict(int)
    for r in closed:
        res_counts[r['resolution_type']] += 1

    print(f"\n--- Resolution Types (closed issues) ---")
    for rtype, count in sorted(res_counts.items(), key=lambda x: -x[1]):
        pct = count / len(closed) * 100 if closed else 0
        print(f"  {rtype}: {count} ({pct:.1f}%)")

    # State reason distribution
    sr_counts = defaultdict(int)
    for r in closed:
        sr_counts[r.get('state_reason') or 'none'] += 1
    print(f"\n--- State Reasons (closed) ---")
    for sr, count in sorted(sr_counts.items(), key=lambda x: -x[1]):
        print(f"  {sr}: {count}")

    # Symptom distribution
    sym_counts = defaultdict(int)
    for r in results:
        for s in r['symptoms']:
            sym_counts[s['type']] += 1
    print(f"\n--- Symptoms ---")
    for stype, count in sorted(sym_counts.items(), key=lambda x: -x[1]):
        print(f"  {stype}: {count}")

    # Workaround types
    wa_counts = defaultdict(int)
    for r in results:
        for w in r['workarounds']:
            wa_counts[w['type']] += 1
    print(f"\n--- Workaround Types ---")
    for wtype, count in sorted(wa_counts.items(), key=lambda x: -x[1]):
        print(f"  {wtype}: {count}")

    # Diagnostic tools
    tool_counts = defaultdict(int)
    for r in results:
        for t in r['diagnostic_tools']:
            tool_counts[t] += 1
    print(f"\n--- Diagnostic Tools Referenced ---")
    for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        print(f"  {tool}: {count}")

    # Time to resolution
    ttrs = [r['time_to_resolution_days'] for r in closed if r['time_to_resolution_days'] is not None]
    if ttrs:
        ttrs.sort()
        print(f"\n--- Time to Resolution (days, closed issues) ---")
        print(f"  Median: {ttrs[len(ttrs)//2]}")
        print(f"  Mean: {sum(ttrs)/len(ttrs):.1f}")
        print(f"  P25: {ttrs[len(ttrs)//4]}")
        print(f"  P75: {ttrs[3*len(ttrs)//4]}")
        print(f"  P90: {ttrs[9*len(ttrs)//10]}")

    # Conversation depth stats
    conv_lengths = [r['conversation_length'] for r in results if r['conversation_length'] > 0]
    if conv_lengths:
        conv_lengths.sort()
        print(f"\n--- Conversation Depth ---")
        print(f"  Issues with comments: {len(conv_lengths)}")
        print(f"  Median comments: {conv_lengths[len(conv_lengths)//2]}")
        print(f"  Mean comments: {sum(conv_lengths)/len(conv_lengths):.1f}")
        print(f"  Max comments: {max(conv_lengths)}")
        print(f"  Issues with 5+ comments: {sum(1 for c in conv_lengths if c >= 5)}")
        print(f"  Issues with 10+ comments: {sum(1 for c in conv_lengths if c >= 10)}")

    print()


if __name__ == "__main__":
    main()
