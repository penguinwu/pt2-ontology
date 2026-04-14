#!/usr/bin/env python3
"""
Phase 1: Heuristic diagnostic workflow extraction from PT2 issues.

Classifies resolution types, extracts workarounds, and identifies
diagnostic patterns from issue bodies and comments.

Usage:
    python extraction/extract_diagnostics.py
    python extraction/extract_diagnostics.py --json
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent


# --- Resolution Type Classification ---

# Ordered by specificity — first match wins
RESOLUTION_CLASSIFIERS = [
    # Duplicate
    (re.compile(r'(?:duplicate|dup)\s+(?:of|issue|#)', re.IGNORECASE), 'duplicate'),
    (re.compile(r'closing\s+as\s+(?:a\s+)?dup', re.IGNORECASE), 'duplicate'),

    # Stale / auto-closed
    (re.compile(r'(?:stale|inactive|no\s+activity)', re.IGNORECASE), 'stale'),
    (re.compile(r'pytorch-bot.*closing.*stale', re.IGNORECASE), 'stale'),

    # Won't fix / by design
    (re.compile(r"(?:won't\s+fix|wontfix|not\s+a\s+bug|by\s+design|expected\s+behavior|working\s+as\s+intended)", re.IGNORECASE), 'wontfix'),
    (re.compile(r"this\s+is\s+(?:expected|intended|correct)\s+behavior", re.IGNORECASE), 'wontfix'),

    # User workaround (config change, code change, no compiler fix)
    (re.compile(r'(?:workaround|work\s+around)\s*(?:is|:|would\s+be|for\s+now)', re.IGNORECASE), 'user_workaround'),
    (re.compile(r'(?:try\s+(?:to\s+)?(?:set(?:ting)?|us(?:e|ing)|switch(?:ing)?|disabl(?:e|ing)))', re.IGNORECASE), 'user_workaround'),

    # User adaptation (upgrade/downgrade)
    (re.compile(r'(?:upgrade|update)\s+(?:to|your|pytorch|torch)', re.IGNORECASE), 'user_adaptation'),
    (re.compile(r'(?:fixed|resolved)\s+(?:in|on)\s+(?:nightly|main|latest|2\.\d+)', re.IGNORECASE), 'user_adaptation'),
    (re.compile(r'(?:this|the\s+issue)\s+(?:is|was|has\s+been)\s+fixed\s+in', re.IGNORECASE), 'user_adaptation'),

    # Compiler fix (PR linked)
    (re.compile(r'(?:fixed|resolved|addressed)\s+(?:by|in|via|with)\s+(?:#|https://github\.com/pytorch/pytorch/pull/)\d+', re.IGNORECASE), 'compiler_fix'),
    (re.compile(r'(?:fix|patch|pr|pull\s+request)\s*(?:#|https://github\.com/pytorch/pytorch/pull/)\d+', re.IGNORECASE), 'compiler_fix'),
    (re.compile(r'https://github\.com/pytorch/pytorch/pull/\d+', re.IGNORECASE), 'compiler_fix'),
    (re.compile(r'(?:merged|landed)\s+(?:the\s+)?(?:fix|pr|patch)', re.IGNORECASE), 'compiler_fix'),
]

# --- Workaround Extraction ---

WORKAROUND_PATTERNS = [
    # Config changes
    (re.compile(r'(torch\._(?:dynamo|inductor)\.config\.\w+\s*=\s*\S+)', re.IGNORECASE), 'config_toggle'),
    (re.compile(r'(TORCHDYNAMO_\w+\s*=\s*\S+)', re.IGNORECASE), 'env_var'),
    (re.compile(r'(TORCHINDUCTOR_\w+\s*=\s*\S+)', re.IGNORECASE), 'env_var'),

    # Compile mode change
    (re.compile(r'(?:try|use|switch\s+to|set)\s+.*(?:mode\s*=\s*["\'](\w+)["\'])', re.IGNORECASE), 'mode_change'),
    (re.compile(r'(?:try|use|switch\s+to)\s+.*(?:backend\s*=\s*["\'](\w+)["\'])', re.IGNORECASE), 'backend_switch'),

    # Disable compile
    (re.compile(r'(?:disable|turn\s+off|remove)\s+(?:torch\.)?compile', re.IGNORECASE), 'disable_compile'),
    (re.compile(r'(?:run|use)\s+(?:in\s+)?eager\s+mode', re.IGNORECASE), 'disable_compile'),

    # Dynamic shapes
    (re.compile(r'(?:mark_dynamic|torch\._dynamo\.mark_dynamic)', re.IGNORECASE), 'guard_adjustment'),
    (re.compile(r'dynamic\s*=\s*True', re.IGNORECASE), 'guard_adjustment'),

    # torch.no_grad
    (re.compile(r'(?:torch\.no_grad|with\s+no_grad|inference_mode)', re.IGNORECASE), 'inference_mode'),

    # Specific op workarounds
    (re.compile(r'(?:replace|use|try)\s+(?:\w+\s+)?(?:instead\s+of|rather\s+than)', re.IGNORECASE), 'op_replacement'),
]

# --- Symptom Classification ---

SYMPTOM_CLASSIFIERS = [
    (re.compile(r'(?:wrong|incorrect|different|mismatch)\s+(?:result|output|answer|value|shape)', re.IGNORECASE), 'wrong_result'),
    (re.compile(r'(?:silent(?:ly)?)\s+(?:wrong|incorrect|produces|returns)', re.IGNORECASE), 'silent_correctness'),
    (re.compile(r'(?:crash|segfault|SIGSEGV|SIGABRT|core\s+dump|illegal\s+instruction)', re.IGNORECASE), 'crash'),
    (re.compile(r'(?:RuntimeError|TypeError|ValueError|AttributeError|AssertionError|KeyError)', re.IGNORECASE), 'error_raised'),
    (re.compile(r'(?:Traceback|traceback|Exception)', re.IGNORECASE), 'error_raised'),
    (re.compile(r'(?:slow|takes?\s+(?:long|forever|minutes|hours))\s*(?:to\s+)?compil', re.IGNORECASE), 'slow_compile'),
    (re.compile(r'(?:compilation|compile)\s+(?:time|is\s+slow|takes)', re.IGNORECASE), 'slow_compile'),
    (re.compile(r'performance\s+(?:regression|degradation|drop)', re.IGNORECASE), 'perf_regression'),
    (re.compile(r'(?:slower|regression)\s+(?:than|compared|vs)\s+(?:eager|without\s+compile)', re.IGNORECASE), 'perf_regression'),
    (re.compile(r'\b(?:hang(?:s|ing|ed)?|stuck|freeze[sd]?|deadlock(?:ed)?|never\s+(?:finish|return|complete))\b', re.IGNORECASE), 'hang'),
    (re.compile(r'(?:OOM|out\s+of\s+memory|memory\s+(?:leak|error|issue))', re.IGNORECASE), 'memory_issue'),
    (re.compile(r'\b(?:flaky|intermittent|non-deterministic)\b', re.IGNORECASE), 'flaky'),
    (re.compile(r'\bgraph\s*break', re.IGNORECASE), 'graph_break'),
    (re.compile(r'\brecompil(?:ation|ing|e)\b', re.IGNORECASE), 'recompilation'),
]

# --- Diagnostic Tool References ---

DIAGNOSTIC_TOOL_PATTERNS = [
    (re.compile(r'TORCH_LOGS', re.IGNORECASE), 'torch_logs'),
    (re.compile(r'torch\._dynamo\.utils\.(?:repro_after|minify)', re.IGNORECASE), 'minifier'),
    (re.compile(r'minif(?:y|ier|ied|ication)', re.IGNORECASE), 'minifier'),
    (re.compile(r'bisect', re.IGNORECASE), 'bisect'),
    (re.compile(r'torch\.compile.*backend\s*=\s*["\']eager["\']', re.IGNORECASE), 'eager_backend'),
    (re.compile(r'aot_eager', re.IGNORECASE), 'aot_eager_backend'),
    (re.compile(r'TORCH_COMPILE_DEBUG', re.IGNORECASE), 'compile_debug'),
    (re.compile(r'torch\._dynamo\.explain', re.IGNORECASE), 'dynamo_explain'),
    (re.compile(r'graph_dump|print_graph|print_tabular', re.IGNORECASE), 'graph_dump'),
]


def load_comments():
    """Load comments indexed by issue number."""
    comments_by_issue = defaultdict(list)
    path = DATA_DIR / "pt2_comments_diagnostic.jsonl"
    if path.exists():
        with open(path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    comments_by_issue[str(d['issue_number'])].append(d)
    return comments_by_issue


def classify_resolution(text, comments_text):
    """Classify the resolution type from combined text."""
    # Check comments first (resolution is usually in later comments)
    for pattern, rtype in RESOLUTION_CLASSIFIERS:
        if pattern.search(comments_text):
            match = pattern.search(comments_text)
            evidence = comments_text[max(0, match.start()-40):match.end()+80].strip()[:200]
            return rtype, evidence

    # Fall back to issue body
    for pattern, rtype in RESOLUTION_CLASSIFIERS:
        if pattern.search(text):
            match = pattern.search(text)
            evidence = text[max(0, match.start()-40):match.end()+80].strip()[:200]
            return rtype, evidence

    return 'unknown', ''


def extract_workarounds(text, comments_text):
    """Extract workaround patterns from text."""
    combined = text + "\n" + comments_text
    workarounds = []
    seen = set()

    for pattern, wtype in WORKAROUND_PATTERNS:
        for match in pattern.finditer(combined):
            snippet = match.group(0)[:150]
            key = f"{wtype}:{snippet[:50]}"
            if key not in seen:
                seen.add(key)
                context = combined[max(0, match.start()-60):match.end()+100].strip()[:250]
                workarounds.append({
                    'type': wtype,
                    'snippet': snippet,
                    'context': context,
                })

    return workarounds


def classify_symptoms(text):
    """Classify symptoms from issue body."""
    symptoms = []
    seen = set()
    for pattern, stype in SYMPTOM_CLASSIFIERS:
        if pattern.search(text) and stype not in seen:
            seen.add(stype)
            match = pattern.search(text)
            evidence = text[max(0, match.start()-30):match.end()+80].strip()[:150]
            symptoms.append({'type': stype, 'evidence': evidence})
    return symptoms


def extract_diagnostic_tools(text, comments_text):
    """Find diagnostic tools referenced in conversation."""
    combined = text + "\n" + comments_text
    tools = set()
    for pattern, tool in DIAGNOSTIC_TOOL_PATTERNS:
        if pattern.search(combined):
            tools.add(tool)
    return sorted(tools)


def extract_fix_prs(text, comments_text):
    """Extract PR numbers that fixed the issue."""
    combined = text + "\n" + comments_text
    pr_pattern = re.compile(r'(?:fixed|resolved|addressed|fix|patch)\s+(?:by|in|via|with)\s+(?:https://github\.com/pytorch/pytorch/pull/|#)(\d+)', re.IGNORECASE)
    pr_link_pattern = re.compile(r'https://github\.com/pytorch/pytorch/pull/(\d+)')

    prs = set()
    for match in pr_pattern.finditer(combined):
        prs.add(int(match.group(1)))
    # Also grab plain PR links from closing comments
    for match in pr_link_pattern.finditer(combined):
        prs.add(int(match.group(1)))

    return sorted(prs)


def process_issue(issue, comments):
    """Extract diagnostic workflow from a single issue."""
    body = issue.get('body', '') or ''
    comments_text = "\n".join(c.get('body', '') or '' for c in comments)

    resolution_type, resolution_evidence = classify_resolution(body, comments_text)
    symptoms = classify_symptoms(body)
    workarounds = extract_workarounds(body, comments_text)
    diagnostic_tools = extract_diagnostic_tools(body, comments_text)
    fix_prs = extract_fix_prs(body, comments_text)

    # Calculate time to resolution
    ttr_days = None
    if issue.get('created_at') and issue.get('closed_at'):
        from datetime import datetime
        try:
            created = datetime.strptime(issue['created_at'], '%Y-%m-%d')
            closed = datetime.strptime(issue['closed_at'], '%Y-%m-%d')
            ttr_days = (closed - created).days
        except (ValueError, TypeError):
            pass

    return {
        'issue_number': issue.get('number', 0),
        'title': issue.get('title', ''),
        'state': issue.get('state', ''),
        'labels': issue.get('labels', ''),
        'author': issue.get('author', ''),
        'comment_count': issue.get('comment_count', 0),
        'resolution_type': resolution_type,
        'resolution_evidence': resolution_evidence,
        'symptoms': symptoms,
        'workarounds': workarounds,
        'diagnostic_tools': diagnostic_tools,
        'fix_prs': fix_prs,
        'time_to_resolution_days': ttr_days,
        'has_conversation': len(comments) > 0,
        'conversation_length': len(comments),
    }


def main():
    output_json = '--json' in sys.argv

    # Load data
    comments_by_issue = load_comments()

    issues = []
    disabled_count = 0
    with open(DATA_DIR / "pt2_issues_closed.jsonl") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                # Skip DISABLED test issues (CI-internal, not user-facing)
                if d.get('title', '').startswith('DISABLED '):
                    disabled_count += 1
                    continue
                issues.append(d)

    print(f"Processing {len(issues)} closed issues (skipped {disabled_count} DISABLED test issues)...", file=sys.stderr)

    results = []
    for issue in issues:
        num = str(issue.get('number', ''))
        comments = comments_by_issue.get(num, [])
        result = process_issue(issue, comments)
        results.append(result)

    if output_json:
        print(json.dumps(results, indent=2))
        return

    # Print report
    print(f"{'='*60}")
    print(f"DIAGNOSTIC WORKFLOW EXTRACTION — Phase 1")
    print(f"{'='*60}")
    print(f"Total closed issues: {len(results)}")
    print(f"Issues with conversations: {sum(1 for r in results if r['has_conversation'])}")

    # Resolution type distribution
    res_counts = defaultdict(int)
    for r in results:
        res_counts[r['resolution_type']] += 1

    print(f"\n--- Resolution Types ---")
    for rtype, count in sorted(res_counts.items(), key=lambda x: -x[1]):
        pct = count / len(results) * 100
        print(f"  {rtype}: {count} ({pct:.1f}%)")

    # Symptom distribution
    sym_counts = defaultdict(int)
    for r in results:
        for s in r['symptoms']:
            sym_counts[s['type']] += 1

    print(f"\n--- Symptoms (from issue bodies) ---")
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
    ttrs = [r['time_to_resolution_days'] for r in results if r['time_to_resolution_days'] is not None]
    if ttrs:
        ttrs.sort()
        print(f"\n--- Time to Resolution (days) ---")
        print(f"  Median: {ttrs[len(ttrs)//2]}")
        print(f"  Mean: {sum(ttrs)/len(ttrs):.1f}")
        print(f"  P25: {ttrs[len(ttrs)//4]}")
        print(f"  P75: {ttrs[3*len(ttrs)//4]}")
        print(f"  P90: {ttrs[9*len(ttrs)//10]}")

    # Top workaround examples
    print(f"\n--- Sample Workarounds ---")
    wa_issues = [r for r in results if r['workarounds'] and r['resolution_type'] == 'user_workaround']
    for r in wa_issues[:5]:
        print(f"\n  #{r['issue_number']}: {r['title'][:70]}")
        for w in r['workarounds'][:2]:
            print(f"    [{w['type']}] {w['snippet'][:100]}")

    # Sample compiler fixes
    print(f"\n--- Sample Compiler Fixes ---")
    fix_issues = [r for r in results if r['resolution_type'] == 'compiler_fix' and r['fix_prs']]
    for r in fix_issues[:5]:
        print(f"\n  #{r['issue_number']}: {r['title'][:70]}")
        print(f"    PRs: {', '.join(f'#{p}' for p in r['fix_prs'])}")
        if r['symptoms']:
            print(f"    Symptoms: {', '.join(s['type'] for s in r['symptoms'])}")

    print()


if __name__ == "__main__":
    main()
