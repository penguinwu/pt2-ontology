#!/bin/bash
# pt2-oss-issues fetch — Download oncall:pt2 issues from GitHub
#
# Usage:
#   fetch.sh                    # Full refresh (all issues)
#   fetch.sh --since 2026-04-01 # Incremental (issues created since date)
#   fetch.sh --count            # Just count total issues
#
# Requires: sudo access, gh CLI, fwdproxy
# Output: DATA_DIR/pytorch-issues-pt2-all.json

set -euo pipefail

DATA_DIR="${PT2_OSS_ISSUES_DIR:-/home/pengwu/projects/pt2-github-issues}"
OUTFILE="$DATA_DIR/pytorch-issues-pt2-all.json"
REPO="pytorch/pytorch"
LABEL="oncall: pt2"
FIELDS="number,title,state,body,comments,labels,assignees,createdAt,updatedAt,closedAt,author,stateReason"

mkdir -p "$DATA_DIR"

# Parse args
MODE="full"
SINCE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --since) SINCE="$2"; MODE="incremental"; shift 2 ;;
    --count) MODE="count"; shift ;;
    --help|-h) echo "Usage: fetch.sh [--since YYYY-MM-DD] [--count]"; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

gh_cmd() {
  sudo bash -c "HTTPS_PROXY=http://fwdproxy:8080 gh $*"
}

if [[ "$MODE" == "count" ]]; then
  COUNT=$(sudo bash -c 'HTTPS_PROXY=http://fwdproxy:8080 gh api "search/issues?q=repo:'"$REPO"'+label:\"oncall:+pt2\"+is:issue&per_page=1" --jq ".total_count"')
  echo "Total oncall:pt2 issues on GitHub: $COUNT"
  if [[ -f "$OUTFILE" ]]; then
    LOCAL=$(python3 -c "import json; print(len(json.load(open('$OUTFILE'))))")
    echo "Local dataset: $LOCAL issues"
    echo "Delta: $((COUNT - LOCAL)) issues"
  fi
  exit 0
fi

# Generate date ranges that each return <1000 results
# GitHub search API caps at 1000 results per query
generate_ranges() {
  if [[ -n "$SINCE" ]]; then
    echo "created:>=$SINCE"
    return
  fi

  python3 -c "
from datetime import date, timedelta

# Quarterly ranges from 2022 to now
start = date(2022, 1, 1)
end = date.today()
ranges = []
current = start

while current < end:
    next_q = current + timedelta(days=90)
    if next_q > end:
        next_q = end
    ranges.append(f'created:{current.isoformat()}..{next_q.isoformat()}')
    current = next_q + timedelta(days=1)

# Add early catch-all
print('created:<=2021-12-31')
for r in ranges:
    print(r)
"
}

echo "Fetching oncall:pt2 issues from $REPO..."
BATCH_DIR=$(mktemp -d)
BATCH_NUM=0
TOTAL=0

while IFS= read -r RANGE; do
  BATCH_FILE="$BATCH_DIR/batch_$BATCH_NUM.json"
  echo -n "  $RANGE → "

  sudo bash -c "HTTPS_PROXY=http://fwdproxy:8080 gh issue list \
    --repo '$REPO' \
    --label '$LABEL' \
    --state all \
    --limit 1000 \
    --search '$RANGE' \
    --json '$FIELDS'" > "$BATCH_FILE" 2>/dev/null

  COUNT=$(python3 -c "import json; print(len(json.load(open('$BATCH_FILE'))))")
  echo "$COUNT issues"

  if [[ "$COUNT" -ge 1000 ]]; then
    echo "    ⚠️  HIT 1000 LIMIT — range needs splitting"
  fi

  TOTAL=$((TOTAL + COUNT))
  BATCH_NUM=$((BATCH_NUM + 1))
done < <(generate_ranges)

echo ""
echo "Merging $BATCH_NUM batches..."

if [[ "$MODE" == "incremental" && -f "$OUTFILE" ]]; then
  # Incremental: merge new issues into existing file
  python3 -c "
import json, glob

existing = json.load(open('$OUTFILE'))
existing_nums = {d['number'] for d in existing}
new_issues = []

for f in sorted(glob.glob('$BATCH_DIR/batch_*.json')):
    batch = json.load(open(f))
    for issue in batch:
        if issue['number'] not in existing_nums:
            new_issues.append(issue)
            existing_nums.add(issue['number'])

all_issues = existing + new_issues
all_issues.sort(key=lambda x: x['number'], reverse=True)
with open('$OUTFILE', 'w') as f:
    json.dump(all_issues, f)

print(f'Added {len(new_issues)} new issues (total: {len(all_issues)})')
"
else
  # Full: merge all batches
  python3 -c "
import json, glob

all_issues = []
seen = set()
for f in sorted(glob.glob('$BATCH_DIR/batch_*.json')):
    batch = json.load(open(f))
    for issue in batch:
        if issue['number'] not in seen:
            seen.add(issue['number'])
            all_issues.append(issue)

all_issues.sort(key=lambda x: x['number'], reverse=True)
with open('$OUTFILE', 'w') as f:
    json.dump(all_issues, f)

print(f'Total unique issues: {len(all_issues)}')
"
fi

# Cleanup
rm -rf "$BATCH_DIR"

# Print summary
python3 -c "
import json, os
data = json.load(open('$OUTFILE'))
from collections import Counter
states = Counter(d.get('state') for d in data)
with_comments = sum(1 for d in data if isinstance(d.get('comments'), list) and len(d['comments']) > 0)
total_comments = sum(len(d.get('comments', [])) for d in data if isinstance(d.get('comments'), list))
fsize = os.path.getsize('$OUTFILE') / 1024 / 1024

print(f'Dataset: {len(data)} issues ({fsize:.1f} MB)')
print(f'States: {dict(states)}')
print(f'Issues with comments: {with_comments}')
print(f'Total inline comments: {total_comments}')
print(f'File: $OUTFILE')
"

echo "Done!"
