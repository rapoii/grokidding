import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import json

PROJECT_DIR = Path(__file__).resolve().parent.parent
USAGE_DB_PATH = PROJECT_DIR / "data" / "usage.db"

def init_db():
    if not USAGE_DB_PATH.parent.exists():
        USAGE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(USAGE_DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY,
                account_id TEXT UNIQUE,
                email TEXT,
                limit_tokens INTEGER,
                used_tokens INTEGER,
                last_updated DATETIME
            )
        """)
        conn.commit()
    finally:
        conn.close()

def _ensure_db():
    """Auto-init DB if it doesn't exist yet."""
    if not USAGE_DB_PATH.exists():
        init_db()

def update_usage(account_id: str, email: str, limit_tokens: int, used_tokens: int):
    _ensure_db()
    conn = sqlite3.connect(USAGE_DB_PATH)
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO usage (account_id, email, limit_tokens, used_tokens, last_updated)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                email = excluded.email,
                limit_tokens = excluded.limit_tokens,
                used_tokens = excluded.used_tokens,
                last_updated = excluded.last_updated
        """, (account_id, email, limit_tokens, used_tokens, now))
        conn.commit()
    finally:
        conn.close()

def get_usage(account_id: str = None):
    _ensure_db()
    conn = sqlite3.connect(USAGE_DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        if account_id:
            row = conn.execute("SELECT * FROM usage WHERE account_id = ?", (account_id,)).fetchone()
            return dict(row) if row else None
        rows = conn.execute("SELECT * FROM usage").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
