Patch 0025 (reupload)
- Diagnostics ('Show resolved creds') never 400s; shows resolved base_url/email and masked token + URL to /myself.
- UI passes optional base_url/email/token from fields so you can test immediately (even if DB retrieval is off).
Files:
- backend/app/api/jira.py
- backend/web/index.html
