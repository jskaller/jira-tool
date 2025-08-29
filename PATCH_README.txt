Patch: jira-tool backend — reports schema & model fixes (2025‑08‑29)

What this fixes
---------------
1) IntegrityErrors on inserts:
   - NOT NULL constraint failed: reports.filters_json / reports.time_mode / reports.owner_id
2) 'owner_id is an invalid keyword argument for Report' (model was missing column)
3) 'Table reports is already defined' metadata clash during import

What changed
------------
- app/db/report_models.py
  • Single authoritative Report model
  • Adds owner_id, filters_json, time_mode (all with NOT NULL-safe defaults)
  • __table_args__ = {extend_existing: True} to tolerate legacy declarations
- scripts/migrate_reports_table.py
  • Idempotent sqlite migration that adds missing columns with sensible defaults

How to apply
------------
1) Drop these files into your backend tree (preserving paths):
   - app/db/report_models.py
   - scripts/migrate_reports_table.py

2) Run the migration once (from the backend folder):
   $ source .venv/bin/activate   # if not already active
   $ python scripts/migrate_reports_table.py

   (If your DB path isn't the default app.db, pass the path explicitly:
    $ python scripts/migrate_reports_table.py /full/path/to/your.db)

3) Start the server as usual:
   $ ./run.sh

Notes
-----
- This patch does not remove any legacy duplicate Report declarations you may have.
  Because __table_args__ uses extend_existing=True, those won't crash import.
  Long‑term, please consolidate to this Report class to avoid subtle mapping issues.

- If you are using foreign keys for owner_id, you can adjust the column to include
  a ForeignKey once the users table is settled. For sqlite this is optional.

- If you previously had an old dev DB missing multiple columns, the migration ensures
  they're added with safe defaults so inserts won't fail.

Reach out if you want me to also include an optional step in run.sh to auto-run the
migration before launching Uvicorn.
