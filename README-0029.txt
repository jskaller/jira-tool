Patch 0029
- Restore a simple **Admin** UI with login + settings and move diagnostics under Admin.
- No backend code changes required.
Files:
- backend/web/index.html   (redirects to /admin.html)
- backend/web/login.html   (calls POST /api/auth/login, stores X-Session token in sessionStorage)
- backend/web/admin.html   (Settings + Diagnostics; uses /api/admin/settings and /api/jira/*)
Usage:
1) Open http://127.0.0.1:8000/login.html
2) Sign in (bootstrap admin: admin@example.com / admin123) -> redirects to /admin.html
3) In Settings, save base URL / email / token; use Diagnostics to verify Jira connectivity.
