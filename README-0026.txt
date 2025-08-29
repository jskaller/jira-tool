Patch 0026
- Fix token discovery: add 'jira_token_encrypted' to synonyms.
- Auto-decrypt token from DB if it looks encrypted (Fernet via APP_SECRET); fallback to raw if decrypt fails.
- New admin-only endpoint: POST /api/jira/diagnostics/save-token {token, base_url?, email?} to store the token into the settings table (prefers *?_encrypted columns).
- UI v0026: adds 'Save token (diagnostics)' button to write the token, then shows updated diagnostics.
Files:
- backend/app/api/jira.py
- backend/web/index.html
