#!/bin/bash
# pt2-oss-issues extract — Run heuristic extraction on the issue corpus
#
# Usage:
#   extract.sh                  # Full extraction
#   extract.sh --stats-only     # Summary stats only
#
# Input:  DATA_DIR/pytorch-issues-pt2-all.json
# Output: ONTOLOGY_DIR/data/diagnostic_extractions_v2.json

set -euo pipefail

DATA_DIR="${PT2_OSS_ISSUES_DIR:-/home/pengwu/projects/pt2-github-issues}"
ONTOLOGY_DIR="/home/pengwu/projects/pt2-ontology"
EXTRACTOR="$ONTOLOGY_DIR/extraction/extract_diagnostics_v2.py"

if [[ ! -f "$DATA_DIR/pytorch-issues-pt2-all.json" ]]; then
  echo "ERROR: No issue data found. Run 'fetch.sh' first."
  exit 1
fi

echo "Running Phase 1 heuristic extraction..."
python3 "$EXTRACTOR" "$@"
echo "Done!"
