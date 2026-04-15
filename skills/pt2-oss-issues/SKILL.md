---
description: >
  Fetch, extract, and analyze PyTorch oncall:pt2 GitHub issues (OSS).
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

### Run extraction

```bash
# Full Phase 1 heuristic extraction
bash /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/extract.sh

# Stats only
bash /home/pengwu/projects/pt2-ontology/skills/pt2-oss-issues/scripts/extract.sh --stats-only
```

## Data Locations

| File | Description |
|------|-------------|
| `/home/pengwu/projects/pt2-github-issues/pytorch-issues-pt2-all.json` | Raw issue corpus (120 MB, ~9,300 issues with inline comments) |
| `/home/pengwu/projects/pt2-ontology/data/diagnostic_extractions_v2.json` | Phase 1 extraction results |
| `/home/pengwu/projects/pt2-ontology/data/phase2_candidates.json` | Issues needing Phase 2 LLM extraction |

## Architecture

```
GitHub API (via sudo + gh CLI + fwdproxy)
    ↓
[fetch.sh] — downloads issues in date-range batches (<1000 per batch)
    ↓
pytorch-issues-pt2-all.json (raw corpus)
    ↓
[extract.sh] → extract_diagnostics_v2.py (heuristic classifiers)
    ↓
diagnostic_extractions_v2.json (structured per-issue extraction)
    ↓
Ontology entities (components, symptoms, configs, fixes, decision tree)
```

## Refresh Schedule

- **Weekly:** Incremental fetch (`--since` last fetch date)
- **Monthly:** Full re-extraction to pick up classifier improvements
- **Ad-hoc:** After major ontology schema changes

## Notes

- `sudo` is required for GitHub API access (bypasses fwdproxy agent filter)
- GitHub search API caps at 1,000 results per query — fetch.sh uses date-range batching
- DISABLED test issues (~2,000) are auto-filtered during extraction
- Comments are embedded inline in the issue JSON (no separate comments file needed)
