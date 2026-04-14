-- Issue-PR Pairing: Extract PR references from closed PT2 issues
-- Sources: issue body + comments mentioning pull request URLs or "Fixes/Closes #N"
-- Used to build ground-truth resolved_by edges in the ontology
-- Source tables: aml.pytorch_github_issues_metadata, aml.pytorch_github_issue_comments

-- Part 1: PR references from issue body
SELECT
    i.number AS issue_id,
    i.title,
    i.state,
    i.labels,
    i.closed_at,
    'body' AS source,
    i.body AS text
FROM aml.pytorch_github_issues_metadata i
WHERE i.ds = (SELECT MAX(ds) FROM aml.pytorch_github_issues_metadata)
  AND i.labels LIKE '%oncall: pt2%'
  AND i.state = 'closed'
  AND (
    i.body LIKE '%/pull/%'
    OR LOWER(i.body) LIKE '%fixes #%'
    OR LOWER(i.body) LIKE '%closes #%'
    OR LOWER(i.body) LIKE '%fixed by%'
  )

UNION ALL

-- Part 2: PR references from comments
SELECT
    CAST(c.issue_number AS BIGINT) AS issue_id,
    i.title,
    i.state,
    i.labels,
    i.closed_at,
    'comment' AS source,
    c.body AS text
FROM aml.pytorch_github_issue_comments c
JOIN aml.pytorch_github_issues_metadata i
  ON CAST(i.number AS VARCHAR) = c.issue_number
WHERE c.ds = (SELECT MAX(ds) FROM aml.pytorch_github_issue_comments)
  AND i.ds = (SELECT MAX(ds) FROM aml.pytorch_github_issues_metadata)
  AND i.labels LIKE '%oncall: pt2%'
  AND i.state = 'closed'
  AND (
    c.body LIKE '%/pull/%'
    OR LOWER(c.body) LIKE '%fixes #%'
    OR LOWER(c.body) LIKE '%closes #%'
    OR LOWER(c.body) LIKE '%fixed by%'
  )
ORDER BY issue_id
