"""
Migration: Add parent-child category hierarchy.

Adds:
- parent_id column (FK → categories.id, nullable)
- is_default column (Boolean, default False)
- Seeds 3 default parent categories
- Assigns existing categories as children of "Lãi suất"

Usage:
    python migrate_parent_child.py
"""

import sqlite3
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

    # Check if parent_id column already exists
    cursor.execute("PRAGMA table_info(categories)")
    columns = [row[1] for row in cursor.fetchall()]

    if "parent_id" in columns:
        print("Column 'parent_id' already exists. Nothing to do.")
        conn.close()
        return

    print("Adding parent-child hierarchy to categories...")

    # Step 1: Add new columns
    cursor.execute("ALTER TABLE categories ADD COLUMN parent_id INTEGER REFERENCES categories(id)")
    cursor.execute("ALTER TABLE categories ADD COLUMN is_default BOOLEAN DEFAULT 0")

    # Step 2: Get existing categories before inserting parents
    cursor.execute("SELECT id, name FROM categories")
    existing_cats = cursor.fetchall()
    print(f"Found {len(existing_cats)} existing categories: {[c[1] for c in existing_cats]}")

    # Step 3: Insert 3 default parent categories
    default_parents = [
        ("Lãi suất", 1),
        ("Các chương trình tín dụng ưu đãi", 2),
        ("Phí dịch vụ", 3),
    ]
    parent_ids = {}
    for name, sort_order in default_parents:
        cursor.execute(
            "INSERT INTO categories (name, parent_id, is_default, sort_order) VALUES (?, NULL, 1, ?)",
            (name, sort_order),
        )
        parent_ids[name] = cursor.lastrowid
        print(f"  Created parent: '{name}' (id={parent_ids[name]})")

    # Step 4: Assign existing categories as children of "Lãi suất" (first parent)
    lai_suat_id = parent_ids["Lãi suất"]
    for cat_id, cat_name in existing_cats:
        cursor.execute(
            "UPDATE categories SET parent_id = ? WHERE id = ?",
            (lai_suat_id, cat_id),
        )
        print(f"  Moved '{cat_name}' under 'Lãi suất'")

    conn.commit()
    conn.close()
    print("Migration complete. Parent-child hierarchy created.")


if __name__ == "__main__":
    migrate()
