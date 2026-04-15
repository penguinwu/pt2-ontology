---
description: >
  Fetch, filter, extract, and analyze PyTorch oncall:pt2 GitHub issues (OSS).
  Use when working on PT2 ontology, analyzing issue patterns, refreshing the issue corpus,
  or extracting diagnostic workflows from GitHub issue conversations.
---

# PT2 OSS Issues Skill

Manage the oncall:pt2 GitHub issue corpus for ontology development.

## Commands

### Fetch issues from GitHub

```bash
# Full refresh (all ~9,300 issues, takes ~5 min)
bash /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/fetch.sh

# Incremental (only new issues since date)
bash /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/fetch.sh --since 2026-04-14

# Count how many issues exist vs local
bash /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/fetch.sh --count
```

### Filter candidates for Phase 2 extraction

```bash
# Full filtering pipeline (label-based)
python3 /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/filter.py

# Stats only (don't overwrite output)
python3 /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/filter.py --stats

# Adjust comment threshold
python3 /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/filter.py --min-comments 7

# Include export issues (for Phase 2 ontology work)
python3 /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/filter.py --include-export

# Include CPU inductor issues
python3 /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/filter.py --include-cpu-inductor
```

### Run Phase 1 heuristic extraction

```bash
# Full extraction
bash /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/extract.sh

# Stats only
bash /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/extract.sh --stats-only
```

## Pipeline

```
GitHub API (via sudo + gh CLI + fwdproxy)
    ↓
[fetch.sh] — downloads issues in date-range batches (<1000 per batch)
    ↓
pytorch-issues-pt2-all.json (raw corpus, ~9,300 issues)
    ↓
[extract.sh] → extract_diagnostics_v2.py (Phase 1: heuristic classifiers)
    ↓
diagnostic_extractions_v2.json (structured per-issue extraction)
    ↓
[filter.py] — label-based candidate selection for Phase 2
    ↓
phase2_candidates_refined.json (~400 torch.compile diagnostic issues)
    ↓
[extract_phase2.py] — Phase 2: LLM-assisted deep extraction
    ↓
phase2_extractions.json → ontology entity updates
```

## Filtering Pipeline (filter.py)

Label-based filters using human-curated oncall labels:

| Filter | What's excluded | Why |
|--------|----------------|-----|
| Resolution | Non-"unknown" Phase 1 results | Already classified by heuristics |
| Comments | <5 comments | Not enough diagnostic content |
| Export | `oncall: export`, `export-triaged` | Export ontology is Phase 2 scope |
| Features | `feature`, `enhancement`, 🚀 body | Not diagnostic conversations |
| CI/Tests | `module: flaky-tests`, `module: ci` | Infrastructure, not compiler bugs |
| Non-compile | `oncall: distributed`, `oncall: jit` | Different domains |
| Platforms | `module: rocm`, `module: xpu`, `module: mps`, `module: windows`, etc. | Phase 2 hardware backend scope |
| CPU Inductor | `oncall: cpu inductor` | Separate backend |
| Process | `good first issue`, `hackathon`, `skipped` | No diagnostic content |
| Docs/Build | `module: docs`, `module: binaries` | Not bugs |

Filtered-out sets are preserved in the full corpus for future phases:
- Export issues → Export sub-ontology (Phase 2)
- Platform issues → Hardware backend user journeys (Phase 2)
- Feature requests → User needs / roadmap signal

## Data Locations

| File | Description |
|------|-------------|
| `/home/pengwu/projects/pt2-github-issues/pytorch-issues-pt2-all.json` | Raw issue corpus (120 MB, ~9,300 issues with inline comments) |
| `/home/pengwu/projects/pt2-ontology/data/diagnostic_extractions_v2.json` | Phase 1 extraction results (7,347 issues) |
| `/home/pengwu/projects/pt2-ontology/data/phase2_candidates_refined.json` | Filtered Phase 2 candidates (~400 issues) |
| `/home/pengwu/projects/pt2-ontology/data/phase2_extractions.json` | Phase 2 deep extractions (iterative) |
| `/home/pengwu/projects/pt2-ontology/data/phase2_iteration_log.md` | Extraction iteration quality log |

### Validate ontology freshness

```bash
# Full validation report
python /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/validate.py

# Summary stats only
python validate.py --stats

# Only show stale/uncertain entities
python validate.py --stale-only

# Check configs against current PyTorch source + update entity files
python validate.py --check-source --update
```

Validation checks:
- **Temporal**: Maps evidence issue dates to PyTorch version eras (pre-2.0 through 2.7)
- **Source**: Greps `fbsource/fbcode/caffe2/torch/` for config names (--check-source)
- **Freshness classification**: living / likely_living / historical / uncertain / base

Each entity gets a `freshness` field: `{status, reason, classified_date}`.
Configs also get a `validation` field: `{status: confirmed|renamed|stale, validated_date}`.

Manual overrides for edge cases go in `FRESHNESS_OVERRIDES` dict in validate.py.

## Refresh Schedule

- **Weekly:** Incremental fetch (`--since` last fetch date)
- **Monthly:** Full re-extraction + re-filter to pick up classifier improvements
- **After extraction batches:** Run `validate.py --check-source --update` to stamp new entities
- **Ad-hoc:** After major ontology schema changes or filter adjustments

## Notes

- `sudo` is required for GitHub API access (bypasses fwdproxy agent filter)
- GitHub search API caps at 1,000 results per query — fetch.sh uses date-range batching
- DISABLED test issues (~2,000) are auto-filtered during extraction
- Comments are embedded inline in the issue JSON (no separate comments file needed)
- All filtering is label-based (human-curated by oncalls) — more reliable than regex heuristics
