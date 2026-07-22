#!/usr/bin/env python3

"""Segmenter: create one SQLite DB per WhatsApp group from the main messages DB.

Usage:
  python3 scripts/segmenter.py            # create per-group DBs under main DB's parent/groups
  GROUP_DB_DIR=/path/to/dir python3 scripts/segmenter.py
  python3 scripts/segmenter.py --dry-run
"""

import sqlite3
import os
import re
import argparse
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path.home() / "whatsapp-summary" / "data" / "messages.db"))
GROUP_DB_DIR = Path(os.getenv("GROUP_DB_DIR", DB_PATH.parent / "groups"))

SANITIZE_RE = re.compile(r"[^A-Za-z0-9_-]+")

SCHEMA = """
CREATE TABLE IF NOT EXISTS "groups" (

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT UNIQUE NOT NULL

);

CREATE TABLE IF NOT EXISTS "messages" (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    group_id TEXT NOT NULL,
    sender TEXT,
    body TEXT,

    message_type TEXT,

    media_path TEXT,
    media_type TEXT,
    media_filename TEXT,

    timestamp INTEGER,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    normalized_content TEXT,

    enrichment_status TEXT DEFAULT 'pending',

    ai_content TEXT,

    ai_metadata TEXT,

    enriched_at DATETIME,

    ocr_text TEXT,
    transcript TEXT,
    ai_caption TEXT,
    last_error TEXT,

    FOREIGN KEY (group_id) REFERENCES groups(group_id)

);
"""


def sanitize_group(group_id: str) -> str:
    if not group_id:
        return "default"
    s = SANITIZE_RE.sub("_", group_id)
    s = s.strip("_")
    return s or "default"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def copy_group(conn, group_id: str, out_db: Path, dry_run: bool = False):
    out_db_parent = out_db.parent
    ensure_dir(out_db_parent)

    print(f"Creating DB for group: '{group_id}' -> {out_db}")

    if dry_run:
        return

    oconn = sqlite3.connect(str(out_db))
    oconn.execute(SCHEMA)

    # Insert the group record first
    oconn.execute("INSERT OR IGNORE INTO groups (group_id) VALUES (?)", (group_id,))
    oconn.commit()

    src = conn.execute("SELECT * FROM messages WHERE group_id=? ORDER BY timestamp", (group_id,))
    rows = src.fetchall()

    if not rows:
        print("  No messages for group, skipping.")
        oconn.close()
        return

    colnames = [description[0] for description in src.description]
    
    # Exclude 'id' to let SQLite auto-generate new IDs in the per-group DB
    colnames_no_id = [c for c in colnames if c != 'id']

    placeholders = ",".join(["?"] * len(colnames_no_id))
    insert_sql = f"INSERT INTO messages ({','.join(colnames_no_id)}) VALUES ({placeholders})"

    values = []
    for r in rows:
        # sqlite3.Row -> sequence works; ensure we extract by column order, skip 'id'
        values.append(tuple(r[col] for col in colnames_no_id))

    oconn.executemany(insert_sql, values)
    oconn.commit()
    oconn.close()

    print(f"  Wrote {len(values)} rows")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done, don't write DBs")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Main DB not found: {DB_PATH}")
        raise SystemExit(1)

    ensure_dir(GROUP_DB_DIR)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Ensure main DB has groups table (optional, for reference)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS "groups" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT UNIQUE NOT NULL
        );
    """)
    conn.commit()

    cur = conn.cursor()
    cur.execute("SELECT DISTINCT group_id FROM messages WHERE group_id IS NOT NULL AND group_id != ''")
    groups = [r[0] for r in cur.fetchall()]

    print(f"Found {len(groups)} groups")

    for gid in groups:
        sanitized = sanitize_group(gid)
        out_db = GROUP_DB_DIR / f"messages_{sanitized}.db"
        copy_group(conn, gid, out_db, dry_run=args.dry_run)

    conn.close()


if __name__ == '__main__':
    main()
