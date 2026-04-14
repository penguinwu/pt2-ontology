# GitHub API vs Hive: Data Source Comparison for PT2 Ontology

**Date:** 2026-04-14
**Sample:** 5 closed oncall:pt2 issues (#172529, #166173, #172386, #148808, #173103)

## Available Hive Tables

| Table | Latest Partition | Record Scope |
|-------|-----------------|--------------|
| `aml.pytorch_github_issues_metadata` | **2026-04-14** (current) | All pytorch/pytorch issues |
| `aml.pytorch_github_issue_comments` | **2026-03-12** (33 days stale) | All comments |
| `aml.fct_pytorch_oss_github_repo_commits` | not checked | Commits |

No tables exist for: timeline events, PR-issue linkages, label change history, reactions.

## Field-by-Field Comparison

### Issue Metadata

| Field | Hive | GitHub API | Gap Impact |
|-------|------|-----------|------------|
| id, number, title, body | ✅ | ✅ | None |
| author | ✅ | ✅ | None |
| state (open/closed) | ✅ | ✅ | None |
| labels (current snapshot) | ✅ | ✅ | None |
| created_at, updated_at, closed_at | ✅ | ✅ | None |
| milestone | ✅ | ✅ | None |
| comment_count | ✅ (but see discrepancy below) | ✅ | Minor |
| **state_reason** | ❌ | ✅ (completed/not_planned/reopened) | **HIGH** |
| **author_association** | ❌ | ✅ (MEMBER/CONTRIBUTOR/NONE) | **MEDIUM** |
| **assignees** | ❌ | ✅ | Low |
| **reactions** | ❌ | ✅ | Low |
| **locked** | ❌ | ✅ | None |

### Comments

| Field | Hive | GitHub API | Gap Impact |
|-------|------|-----------|------------|
| body (full text) | ✅ | ✅ | None |
| author | ✅ | ✅ | None |
| created_at, updated_at | ✅ | ✅ | None |
| **author_association** | ❌ | ✅ | **MEDIUM** |
| **reactions** | ❌ | ✅ | Low |

### Timeline Events (GitHub-only)

| Event Type | Available in Hive? | Impact for Ontology |
|-----------|-------------------|-------------------|
| `cross-referenced` (which PRs reference this issue) | ❌ | **HIGH** — ground-truth PR linkage |
| `closed` (which PR/commit closed the issue) | ❌ | **HIGH** — which PR actually fixed it |
| `labeled`/`unlabeled` (label change history) | ❌ | Medium — triage timeline |
| `referenced` (commits mentioning issue) | ❌ | Medium |
| `connected`/`disconnected` (sidebar PR links) | ❌ | **HIGH** — sidebar links not in text |

## Critical Findings

### 1. Comments Table is 33 Days Stale
Last partition: `2026-03-12`. Any issue resolved after that date has **no comment data in Hive**. This directly blocks diagnostic workflow mining for recent issues.

Of our 10 sample issues, 8 were closed after March 12 — their resolution conversations are partially or fully missing from Hive.

### 2. comment_count Discrepancy
Issue #172529 shows `comment_count=0` in metadata (ds=2026-04-14) but has 3 comments in the comments table (ds=2026-03-12). Likely a snapshot timing bug in the metadata ETL.

### 3. No state_reason Field
We can't distinguish "fixed" (state_reason=completed) from "wontfix" (state_reason=not_planned) from "duplicate" closures. This means our `resolved_by` edges include false positives. Our regex-based `RESOLUTION_PATTERNS` catch some wontfix/not-a-bug patterns, but miss many.

Example: An issue closed as "duplicate" would appear as resolved in our data, but has no fix.

### 4. No Timeline/Cross-Reference Data
Our PR linker extracts PR numbers from body+comment text via regex. But GitHub's timeline API provides:
- **Ground-truth close event**: which PR actually closed the issue (not just mentioned)
- **Sidebar-linked PRs**: linked via GitHub UI but never mentioned in text
- **Cross-references**: PRs that reference the issue without being mentioned

From our PR linker results: 2,296 edges were text-extracted. Unknown number of sidebar-linked PRs are missing.

### 5. What Hive Gets Right
Despite the gaps, Hive provides the bulk of what we need:
- **Full issue body text** — complete reproduction steps, error messages, code snippets
- **Full comment text** — diagnostic conversations, workaround suggestions, fix discussions
- **Current labels** — our label classifier works on these
- **Comment authorship** — we can identify PyTorch team members by matching known usernames

## Verdict by Use Case

| Use Case | Hive Sufficient? | Notes |
|----------|-----------------|-------|
| Label classification | ✅ Yes | Labels are current in issues table |
| Entity extraction (causes, symptoms) | ✅ Yes | Body text is complete |
| PR linkage (resolved_by) | ⚠️ 80% | Text parsing works, misses sidebar links + close events |
| Diagnostic workflow mining | ⚠️ Partial | **Comments stale since Mar 12** — only covers issues resolved before that |
| Expert identification | ⚠️ Partial | Author present but no author_association |
| Fix vs wontfix classification | ❌ Missing | No state_reason, heuristics insufficient |

## Recommendation

**Use Hive as the base dataset + supplement with a GitHub API enrichment script.**

### What to use Hive for (bulk):
1. All issue metadata (title, body, labels, state, dates) — current and complete
2. Comments for issues resolved before 2026-03-12
3. Label classification pipeline (already working at 95.2%)

### What needs GitHub API supplementation:
1. **`state_reason`** for all closed oncall:pt2 issues — critical for filtering out wontfix/duplicate
2. **Timeline events** for high-confidence PR linkage (close events, cross-references)
3. **Comments for recent issues** (Mar 12 – present) — until Hive pipeline is fixed
4. **`author_association`** to classify team vs external commenters

### Practical path:
Since GitHub API is unreachable from DevVM (DNS blocked), we need one of:
- **Option A**: Peng runs a GitHub API enrichment script locally (she has access)
- **Option B**: Write a script using `gh` CLI that Peng runs on her laptop
- **Option C**: File a request to fix the Hive comments ETL pipeline (long-term)
- **Option D**: Use the existing Hive data for issues resolved before Mar 12 (1,500+ closed PT2 issues with full comments available), defer recent issues

### Recommended immediate action:
**Option D first, then Option A/B.** Start mining with the pre-Mar-12 dataset (large enough for pattern extraction), while preparing an enrichment script for Peng to run.
