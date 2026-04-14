-- J6 Compile-Time Performance: Issues where compilation takes too long
-- Labels: module: compile-time (accuracy TBD per Issue Health doc)
-- Also captures title-pattern matches for compile time issues
-- Source: aml.pytorch_github_issues_metadata (daily-refreshed)
-- Excludes holdout period (Feb-Apr 2026) for validation

SELECT
    number AS issue_id,
    title,
    state,
    labels,
    created_at,
    updated_at
FROM aml.pytorch_github_issues_metadata
WHERE ds = (SELECT MAX(ds) FROM aml.pytorch_github_issues_metadata)
  AND labels LIKE '%oncall: pt2%'
  AND (
    -- Label-based classification
    labels LIKE '%module: compile-time%'
    OR labels LIKE '%compile-cache%'
    -- Title-pattern fallback
    OR LOWER(title) LIKE '%compile time%'
    OR LOWER(title) LIKE '%compilation time%'
    OR LOWER(title) LIKE '%slow compilation%'
    OR LOWER(title) LIKE '%compilation takes%'
    OR LOWER(title) LIKE '%cold start%'
    OR LOWER(title) LIKE '%warm start%'
    OR LOWER(title) LIKE '%recompil%'
    OR LOWER(title) LIKE '%too many recompilations%'
    OR LOWER(title) LIKE '%compile is slow%'
    OR LOWER(title) LIKE '%long to compile%'
  )
  -- Exclude noise categories
  AND labels NOT LIKE '%oncall: cpu inductor%'
  AND labels NOT LIKE '%module: flaky-tests%'
  AND labels NOT LIKE '%skipped%'
  -- Exclude holdout period
  AND created_at < '2026-02-01'
ORDER BY created_at DESC
