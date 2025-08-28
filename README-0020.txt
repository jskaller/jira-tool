Patch 0020
- Fixes a JavaScript syntax error in Admin → Ingest Jira handler that broke the entire script, which made the Login button appear non-functional.
- Replaced Python-style `or None` with JavaScript `|| null`.
Files:
- backend/web/index.html
