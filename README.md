# Patch README

This patch addresses the errors you hit when working with the `reports` feature:

- `no such column: reports.name`
- `NOT NULL constraint failed: reports.owner_id`
- `NOT NULL constraint failed: reports.filters_json`
- `NOT NULL constraint failed: reports.time_mode`
- `Table 'reports' is already defined for this MetaData instance.`

## What's included

- `backend/scripts/migrate_reports_table.py`  
  Idempotent SQLite migration that **adds any missing columns** with safe defaults:

    - `name TEXT NOT NULL DEFAULT ''`
    - `owner_id INTEGER`
    - `filters_json TEXT NOT NULL DEFAULT '{}'`
    - `time_mode TEXT NOT NULL DEFAULT 'updated'`

- `backend/app/db/report_models.py`  
  Updated ORM model with `__table_args__ = {'extend_existing': True}` to avoid duplicate table definition during reloads, and server-side defaults for all NOT NULL fields.

## How to apply

1. Extract this zip into the **application top directory** (same folder that contains `backend/`).  
   It will place files under `backend/scripts/` and `backend/app/db/`.

2. Run the migration (from within `backend/`):  
   ```bash
   python3 scripts/migrate_reports_table.py ./app.db
   ```
   You should see a backup like `app.db.bak_YYYYMMDD_HHMMSS` and any applied `ALTER TABLE` lines.
   If everything already exists, it'll say: *No changes needed.*

3. Restart your backend:  
   ```bash
   ./run.sh
   ```

> If you still see a NOT NULL error on insert after this, your API layer may not be populating fields like `filters_json` or `time_mode` on new `Report()` objects. The model and DB now both have defaults (`{}` and `updated`), so inserts without those should succeed. If your code explicitly sets these to `None`, remove that or set them to the defaults.
