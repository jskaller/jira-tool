#!/usr/bin/env python3
"""SQLite migration helper for the `reports` table.

- Adds any missing columns (idempotent).
- Ensures NOT NULL columns have a usable DEFAULT so inserts from the API
  don't fail if a value isn't provided.
- Back-fills NULLs with safe values.
Usage:
    python3 scripts/migrate_reports_table.py /path/to/app.db
"""
from __future__ import annotations

import sqlite3
import sys
from typing import Dict, Tuple

REQUIRED_COLUMNS: Dict[str, Tuple[str, str | None, bool]] = {
    # name: (sqlite_type, default_sql_literal, not_null)
    # NOTE: defaults must be *SQL literals*, e.g. '90', "'{}'", "''"
    "owner_id": ("INTEGER", None, False),
    "name": ("TEXT", "''", True),
    "params_json": ("TEXT", "'{}'", True),
    "filters_json": ("TEXT", "'{}'", True),
    "window_days": ("INTEGER", "90", True),
    "business_mode": ("TEXT", "'wall'", True),
    "aggregate_by": ("TEXT", "'both'", True),
    "time_mode": ("TEXT", "'updated'", True),
    "csv_path": ("TEXT", "''", True),
}

FILL_NULLS_SQL = [
    "UPDATE reports SET filters_json='{}' WHERE filters_json IS NULL;",
    "UPDATE reports SET time_mode='updated' WHERE time_mode IS NULL;",
    "UPDATE reports SET params_json='{}' WHERE params_json IS NULL;",
    "UPDATE reports SET business_mode='wall' WHERE business_mode IS NULL;",
    "UPDATE reports SET aggregate_by='both' WHERE aggregate_by IS NULL;",
    "UPDATE reports SET window_days=90 WHERE window_days IS NULL;",
    # Give unnamed rows a readable fallback
    "UPDATE reports SET name='report ' || id WHERE name IS NULL OR name='';",
    "UPDATE reports SET csv_path='' WHERE csv_path IS NULL;",
]

def get_existing_columns(conn: sqlite3.Connection) -> dict[str, dict]:
    cur = conn.execute("PRAGMA table_info('reports')")
    cols: dict[str, dict] = {}
    for cid, name, ctype, notnull, dflt_value, pk in cur.fetchall():
        cols[name] = {
            "type": ctype,
            "notnull": bool(notnull),
            "default": dflt_value,
            "pk": bool(pk),
        }
    return cols

def add_column(conn: sqlite3.Connection, name: str, col_type: str, default_sql: str | None, not_null: bool) -> None:
    pieces = [f"ALTER TABLE reports ADD COLUMN {name} {col_type}"]
    if not_null:
        # For NOT NULL in SQLite, a DEFAULT is required at ADD COLUMN time
        if default_sql is None:
            # If no default is specified for a NOT NULL column, make it empty string / zero by type
            default_sql = "''" if col_type == "TEXT" else "0"
        pieces.append(f"DEFAULT {default_sql} NOT NULL")
    elif default_sql is not None:
        pieces.append(f"DEFAULT {default_sql}")
    sql = " ".join(pieces) + ";"
    conn.execute(sql)

def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF;")
        existing = get_existing_columns(conn)

        # Verify table exists
        if not existing:
            raise SystemExit("ERROR: 'reports' table not found in this database.")

        added_any = False
        for name, (ctype, default_sql, not_null) in REQUIRED_COLUMNS.items():
            if name not in existing:
                add_column(conn, name, ctype, default_sql, not_null)
                added_any = True

        # Backfill NULLs to keep future inserts happy
        for sql in FILL_NULLS_SQL:
            conn.execute(sql)

        conn.commit()
        if added_any:
            print("Migration complete: added missing columns and backfilled NULLs.")
        else:
            print("Schema OK: no columns were missing. Ensured NULLs are filled.")
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/migrate_reports_table.py /path/to/app.db")
        raise SystemExit(2)
    migrate(sys.argv[1])
