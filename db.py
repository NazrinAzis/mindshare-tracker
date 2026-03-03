"""
db.py — SQLite connection and initialization helper
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "mindshare.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-like access: row["column_name"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate_db():
    """Add new columns to existing tables (idempotent)."""
    with get_connection() as conn:
        for col, definition in [
            ("tiktok_score_normalized", "REAL"),
            ("tiktok_weight", "REAL DEFAULT 0.10"),
        ]:
            try:
                conn.execute(f"ALTER TABLE mindshare_scores ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass  # column already exists


def init_db():
    """Create tables and seed initial data from schema.sql"""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
    migrate_db()
    print(f"✅ Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
