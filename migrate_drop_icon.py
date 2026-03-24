"""
Migration: Drop 'icon' column from 'categories' table.

SQLite does not support DROP COLUMN before version 3.35.0.
This script recreates the table without the icon column.

Usage:
    python migrate_drop_icon.py
"""

import sqlite3
import sys
import shutil
from datetime import datetime

DB_PATH = "instance/database.db"


def migrate():
    # Backup first
    backup_path = f"{DB_PATH}.backup-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if icon column exists
    cursor.execute("PRAGMA table_info(categories)")
    columns = [row[1] for row in cursor.fetchall()]

    if "icon" not in columns:
        print("Column 'icon' does not exist. Nothing to do.")
        conn.close()
        return

    print("Dropping 'icon' column from 'categories' table...")

    # SQLite approach: recreate table without the column
    cursor.executescript("""
        BEGIN TRANSACTION;

        CREATE TABLE categories_new (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at DATETIME
        );

        INSERT INTO categories_new (id, name, sort_order, created_at)
        SELECT id, name, sort_order, created_at FROM categories;

        DROP TABLE categories;

        ALTER TABLE categories_new RENAME TO categories;

        COMMIT;
    """)

    conn.close()
    print("Migration complete. 'icon' column removed.")


if __name__ == "__main__":
    migrate()
