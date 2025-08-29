# scripts/migrate_reports_table.py
# Idempotent helper to ensure the 'reports' table has the columns
# our API expects — especially useful for pre-existing dev databases.
#
# Usage (from backend dir):
#   python scripts/migrate_reports_table.py  [path_to_sqlite_db (default: app.db)]
#
# Safe to run multiple times.

import os
import sqlite3
import sys

def colset(conn, table):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}

def add_col(conn, table, col_sql):
    # col_sql is of the form: 'ALTER TABLE reports ADD COLUMN ...;'
    conn.execute(col_sql)

def ensure_reports_schema(db_path: str):
    if not os.path.exists(db_path):
        print(f"[migrate] {db_path} does not exist yet. Nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reports'")
        row = cur.fetchone()
        if not row:
            print("[migrate] 'reports' table not found; skipping (fresh DB will be created by ORM on first use).")
            return

        have = colset(conn, "reports")

        # Each entry: (column_name, alter_table_sql)
        wanted = [
            ("owner_id",      "ALTER TABLE reports ADD COLUMN owner_id INTEGER NOT NULL DEFAULT 0"),
            ("name",          "ALTER TABLE reports ADD COLUMN name TEXT NOT NULL DEFAULT 'untitled'"),
            ("params_json",   "ALTER TABLE reports ADD COLUMN params_json TEXT NOT NULL DEFAULT '{}'"),
            ("filters_json",  "ALTER TABLE reports ADD COLUMN filters_json TEXT NOT NULL DEFAULT '{}'"),
            ("window_days",   "ALTER TABLE reports ADD COLUMN window_days INTEGER NOT NULL DEFAULT 180"),
            ("business_mode", "ALTER TABLE reports ADD COLUMN business_mode TEXT NOT NULL DEFAULT 'both'"),
            ("aggregate_by",  "ALTER TABLE reports ADD COLUMN aggregate_by TEXT NOT NULL DEFAULT 'both'"),
            ("time_mode",     "ALTER TABLE reports ADD COLUMN time_mode TEXT NOT NULL DEFAULT 'updated'"),
            ("csv_path",      "ALTER TABLE reports ADD COLUMN csv_path TEXT NOT NULL DEFAULT ''"),
        ]

        changed = False
        for col, stmt in wanted:
            if col not in have:
                print(f"[migrate] Adding missing column: {col}")
                add_col(conn, "reports", stmt)
                changed = True

        if changed:
            conn.commit()
            print("[migrate] reports table updated ✅")
        else:
            print("[migrate] reports table already up-to-date ✅")

    finally:
        conn.close()

def main():
    db_path = None
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Try to derive from DATABASE_URL if present, else default to 'app.db'
        url = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
        if url and url.startswith("sqlite"):
            # Accept forms like sqlite:///app.db or sqlite+aiosqlite:///app.db
            parts = url.split(":///")
            if len(parts) == 2:
                db_path = parts[1]
        if not db_path:
            db_path = "app.db"

    ensure_reports_schema(db_path)

if __name__ == "__main__":
    main()
