Patch 0032
Adds first-cut **Reporting Engine** (backend + UI).

Backend:
- `/api/reports/run` — builds timelines from stored Jira transitions, computes per-status durations
  (both wall and business hours), stores results, and writes CSV to `storage/reports/report_<id>.csv`.
- `/api/reports` — list reports.
- `/api/reports/{id}` DELETE — delete report (and its rows/stats).
- `/api/reports/{id}/csv` — download CSV.
- Business-hours math in `services/business_time.py` (timezone-aware, Mon–Fri 9–5 by default).
- Models in `db/report_models.py`.

UI (Admin → Reports tab):
- Run a report (name, projects, window, business mode, aggregate-by).
- List previous reports, download CSV, delete.

CSV v1 schema (one row per issue+status):
`issue_key, project_key, issue_type, assignee, parent_key, epic_key, bucket, status, entered_count, wall_hours, business_hours`

Notes / next steps:
- Category aggregation & rollups (epic/parent totals) can be added on top.
- Interactive charts to visualize time-in-status will come after we agree on chart specs.
