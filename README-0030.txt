Patch 0030
- Restore **Sign in** page at /login.html (root / redirects there).
- Admin UI expanded to include ALL core settings we previously discussed:
  - Jira base URL, email, API token
  - Default window (days), business hours start/end, business days, timezone
  - Aggregation controls (mode + custom categories textarea; client-side for now)
- Users tab: list/create/edit/delete users via /api/users endpoints.
- Ingest tab: run POST /api/jira/ingest with projects/labels/JQL/window/max.
- Diagnostics tab retained.

Files:
- backend/web/index.html
- backend/web/login.html
- backend/web/admin.html
