-- J3 Correctness & Debugging: Issues where compiled model gives different results
-- Labels: module: pt2 accuracy, module: correctness (silent)
-- Also captures title-pattern matches for correctness issues without labels
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
    -- Label-based classification (high confidence)
    labels LIKE '%module: pt2 accuracy%'
    OR labels LIKE '%module: correctness (silent)%'
    -- Title-pattern fallback (lower confidence, for coverage)
    OR LOWER(title) LIKE '%wrong result%'
    OR LOWER(title) LIKE '%incorrect result%'
    OR LOWER(title) LIKE '%correctness%'
    OR LOWER(title) LIKE '%numerical mismatch%'
    OR LOWER(title) LIKE '%silent correctness%'
    OR LOWER(title) LIKE '%produces different%'
    OR LOWER(title) LIKE '%different output%'
    OR LOWER(title) LIKE '%accuracy%'
  )
  -- Exclude noise categories (from Issue Health doc)
  AND labels NOT LIKE '%oncall: cpu inductor%'
  AND labels NOT LIKE '%module: flaky-tests%'
  AND labels NOT LIKE '%skipped%'
  -- Exclude holdout period
  AND created_at < '2026-02-01'
ORDER BY created_at DESC
