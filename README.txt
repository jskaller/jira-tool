jira-tool backend patch (generated 2025-08-29T16:35:17.997032Z)

Files included (drop-in replacements; paths are from repo root):
- backend/app/db/report_models.py
- backend/app/api/reports.py

What this fixes:
- "TypeError: 'owner_id' is an invalid keyword argument for Report"
- sqlite3.IntegrityError NOT NULL failures for: filters_json, time_mode, owner_id
- Prior "no such column" errors for reports.name are handled by explicit fields

Notes:
- If your project uses a different session dependency than app.db.session.get_session,
  this module falls back to a local sqlite+aiosqlite session (DATABASE_URL env can override).
- If your auth layer provides a current user id, set `owner_id = <user.id>` in POST /run.

How to deploy:
1) Back up your current files (git commit or copy them aside).
2) Extract the zip at repo root so the paths line up and overwrite the two files.
3) Restart the backend with ./run.sh
4) Verify:
   - GET /api/reports returns 200
   - POST /api/reports/run returns 200/{id: ..., status: 'queued'}

If you prefer a surgical change instead of replacing your reports.py,
copy only report_models.py and then ensure your run_report() sets:
    owner_id (non-null), filters_json (json string), time_mode ('updated')
