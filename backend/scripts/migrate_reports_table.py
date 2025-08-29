#!/usr/bin/env python3
"""
Safe, idempotent SQLite migration for the `reports` table.

Usage:
  python backend/scripts/migrate_reports_table.py /absolute/path/to/app.db
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any

REQUIRED_COLS: Dict[str, str] = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "created_at": "DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)",
    "owner_id": "INTEGER NOT NULL DEFAULT 1",
    "name": "TEXT NOT NULL DEFAULT ''",
    "params_json": "TEXT NOT NULL DEFAULT '{}'",
    "filters_json": "TEXT NOT NULL DEFAULT '{}'",
    "window_days": "INTEGER NOT NULL DEFAULT 180",
    "business_mode": "TEXT NOT NULL DEFAULT 'both'",
    "aggregate_by": "TEXT NOT NULL DEFAULT 'both'",
    "time_mode": "TEXT NOT NULL DEFAULT 'both'",
    "csv_path": "TEXT NOT NULL DEFAULT ''",
}

def ensure_table(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            owner_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL DEFAULT '',
            params_json TEXT NOT NULL DEFAULT '{}',
            filters_json TEXT NOT NULL DEFAULT '{}',
            window_days INTEGER NOT NULL DEFAULT 180,
            business_mode TEXT NOT NULL DEFAULT 'both',
            aggregate_by TEXT NOT NULL DEFAULT 'both',
            time_mode TEXT NOT NULL DEFAULT 'both',
            csv_path TEXT NOT NULL DEFAULT ''
        );
        """
    )
    conn.commit()

def existing_columns(conn: sqlite3.Connection) -> Dict[str, Any]:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(reports)")
    cols = {}
    for cid, name, coltype, notnull, dflt_value, pk in cur.fetchall():
        cols[name] = {
            "type": coltype,
            "notnull": bool(notnull),
            "default": dflt_value,
            "pk": bool(pk),
        }
    return cols

def add_missing_columns(conn: sqlite3.Connection, cols_present: Dict[str, Any]) -> int:
    missing = [c for c in REQUIRED_COLS.keys() if c not in cols_present]
    cur = conn.cursor()
    for col in missing:
        ddl = f"ALTER TABLE reports ADD COLUMN {col} {REQUIRED_COLS[col]}"
        cur.execute(ddl)
        print(f"Added column: {col}")
    if missing:
        conn.commit()
    return len(missing)

def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python backend/scripts/migrate_reports_table.py /absolute/path/to/app.db")
        return 2

    db_path = Path(sys.argv[1])
    if not db_path.exists():
        print(f"ERROR: DB path not found: {db_path}")
        return 2

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_table(conn)
        cols = existing_columns(conn)
        added = add_missing_columns(conn, cols)
        print(f"Migration complete. Columns added: {added}")
    finally:
        conn.close()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
