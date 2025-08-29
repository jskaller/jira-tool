
# Backend Patch — Reports Table Migration

**Files included**
- `scripts/migrate_reports_table.py` — SQLite migration (idempotent).

**How to apply**
1. Copy `scripts/migrate_reports_table.py` into your repo at `backend/scripts/`.
2. Run the migration (from the backend root):
   ```bash
   python3 scripts/migrate_reports_table.py ./app.db
   ```
3. Restart your server:
   ```bash
   ./run.sh
   ```
