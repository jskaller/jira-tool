#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Safe SQLite migration for the `reports` table.

Adds any missing columns with sane defaults, without dropping data.
Usage:
  python3 backend/scripts/migrate_reports_table.py backend/app.db
"""

import sys
import os
import sqlite3
from typing import Set

REQUIRED_COLS = {
    "id",
    "created_at",
    "owner_id",
    "name",
    "params_json",
    "filters_json",
    "window_days",
    "business_mode",
    "aggregate_by",
    "time_mode",
    "csv_path",
}

# column DDL snippets keyed by column name
DDL = {
    "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
    "owner_id": "INTEGER NULL",
    "name": "TEXT NOT NULL DEFAULT 'report'",
    "params_json": "TEXT NOT NULL DEFAULT '{}'",
    "filters_json": "TEXT NOT NULL DEFAULT '{}'",
    "window_days": "INTEGER NOT NULL DEFAULT 180",
    "business_mode": "TEXT NOT NULL DEFAULT 'both'",
    "aggregate_by": "TEXT NOT NULL DEFAULT 'both'",
    "time_mode": "TEXT NOT NULL DEFAULT 'both'",
    "csv_path": "TEXT NOT NULL DEFAULT ''",
}

def table_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    cur = conn.execute(f"PRAGMA table_info({table});")
    return {row[1] for row in cur.fetchall()}

def add_column(conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    sql = f"ALTER TABLE {table} ADD COLUMN {name} {ddl};"
    conn.execute(sql)

def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: migrate_reports_table.py <path-to-sqlite-db>")
        return 2
    db_path = sys.argv[1]
    if not os.path.exists(db_path):
        print(f"Error: DB not found at {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF;")
        conn.execute("BEGIN;")

        existing = table_columns(conn, "reports")
        missing = [c for c in REQUIRED_COLS if c not in existing]

        if not missing:
            print("reports table already has required columns. No changes.")
        else:
            for col in missing:
                if col == "id":
                    # assume primary key already exists if table exists
                    continue
                ddl = DDL.get(col)
                if not ddl:
                    continue
                print(f"Adding column: {col} ...")
                add_column(conn, "reports", col, ddl)

        conn.commit()
        print("Migration complete.")
        return 0
    except Exception as e:
        conn.rollback()
        print("Migration failed:", e)
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
