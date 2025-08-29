# Idempotent SQLite migration for the 'reports' table.
# Adds any missing NOT NULL columns with safe defaults so existing code paths
# stop failing with sqlite3.IntegrityError and OperationalError.

from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "app.db"

def get_cols(conn: sqlite3.Connection) -> set[str]:
    cur = conn.execute("PRAGMA table_info(reports)")
    return {row[1] for row in cur.fetchall()}

def ensure_table_exists(conn: sqlite3.Connection) -> None:
    # Create a minimal table if it doesn't exist (keeps id/created_at stable).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reports ( "
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    conn.commit()

def add_column(conn: sqlite3.Connection, sql: str) -> None:
    conn.execute(sql)
    conn.commit()

def main(db_path: str | None = None) -> None:
    db_file = Path(db_path) if db_path else DEFAULT_DB
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    try:
        ensure_table_exists(conn)
        have = get_cols(conn)

        if "name" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN name TEXT NOT NULL DEFAULT 'untitled'")
        if "owner_id" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN owner_id INTEGER NULL")
        if "params_json" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN params_json TEXT NOT NULL DEFAULT '{}'")
        if "filters_json" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN filters_json TEXT NOT NULL DEFAULT '{}'")
        if "window_days" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN window_days INTEGER NOT NULL DEFAULT 90")
        if "business_mode" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN business_mode TEXT NOT NULL DEFAULT 'wall'")
        if "aggregate_by" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN aggregate_by TEXT NOT NULL DEFAULT 'both'")
        if "time_mode" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN time_mode TEXT NOT NULL DEFAULT 'updated'")
        if "csv_path" not in have:
            add_column(conn, "ALTER TABLE reports ADD COLUMN csv_path TEXT NOT NULL DEFAULT ''")

        print(f"Migration complete. DB: {db_file}")
    finally:
        conn.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
