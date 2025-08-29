#!/usr/bin/env python3
"""
Idempotent SQLite migration for the `reports` table.
- Adds any missing columns with safe NOT NULL defaults.
- Backfills NULLs on existing rows.
Usage:
    python3 backend/scripts/migrate_reports_table.py /absolute/path/to/app.db
"""
from __future__ import annotations
import sqlite3, sys, os

REQUIRED = {
    "id": None,  # primary key assumed to exist already
    "created_at": "DATETIME NOT NULL DEFAULT (datetime('now'))",
    "owner_id": "INTEGER NOT NULL DEFAULT 1",
    "name": "TEXT NOT NULL DEFAULT ''",
    "params_json": "TEXT NOT NULL DEFAULT '{}'",
    "filters_json": "TEXT NOT NULL DEFAULT '{}'",
    "time_mode": "TEXT NOT NULL DEFAULT 'updated'",
    "window_days": "INTEGER NOT NULL DEFAULT 180",
    "business_mode": "TEXT NOT NULL DEFAULT 'both'",
    "aggregate_by": "TEXT NOT NULL DEFAULT 'both'",
    "csv_path": "TEXT NOT NULL DEFAULT ''",
}

BACKFILL = {
    "owner_id": "1",
    "name": "''",
    "params_json": "'{}'",
    "filters_json": "'{}'",
    "time_mode": "'updated'",
    "window_days": "180",
    "business_mode": "'both'",
    "aggregate_by": "'both'",
    "csv_path": "''",
}

def die(msg: str, code: int = 1) -> None:
    print(f"[migrate] ERROR: {msg}")
    sys.exit(code)

def info(msg: str) -> None:
    print(f"[migrate] {msg}")

def table_exists(cur, name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,))
    return cur.fetchone() is not None

def columns(cur, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table});")
    return {row[1] for row in cur.fetchall()}  # row[1] is "name"

def add_column(conn, table: str, name: str, ddl: str) -> None:
    if ddl is None:
        return
    with conn:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl};")

def backfill_null(conn, table: str, name: str, default_sql: str) -> None:
    with conn:
        conn.execute(f"UPDATE {table} SET {name} = {default_sql} WHERE {name} IS NULL;")

def main() -> None:
    if len(sys.argv) != 2:
        die("Usage: python3 backend/scripts/migrate_reports_table.py /absolute/path/to/app.db")

    db_path = sys.argv[1]
    if not os.path.isabs(db_path):
        die("Please supply an ABSOLUTE path to the SQLite database file.")
    if not os.path.exists(db_path):
        die(f"Database file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if not table_exists(cur, "reports"):
        die("Table 'reports' does not exist in this database. Start the app once to initialize it.")

    existing = columns(cur, "reports")
    info(f"Existing columns: {sorted(existing)}")

    # Add missing columns
    for col, ddl in REQUIRED.items():
        if col not in existing:
            info(f"Adding missing column: {col}")
            add_column(conn, "reports", col, ddl)

    # Backfill any NULLs for critical columns to satisfy NOT NULL constraints
    for col, default_sql in BACKFILL.items():
        info(f"Backfilling NULLs for: {col}")
        backfill_null(conn, "reports", col, default_sql)

    info("Migration complete ✔")

if __name__ == "__main__":
    main()
