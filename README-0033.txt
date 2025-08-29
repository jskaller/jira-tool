Patch 0033
Fix reports backend to avoid relying on a `JiraIssue.transitions` ORM relationship.

- Bulk-load `JiraTransition` rows by `issue_key` (or `issue_id` if that's what's present),
  then group in Python, so it works with the ingestion schema you already have.
- Removes the `.options(joinedload(...))` call that caused:
  `AttributeError: type object 'JiraIssue' has no attribute 'transitions'`

Files:
- backend/app/api/reports.py (patched)
