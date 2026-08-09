"""Session statistics tracker — persists farming session history to data/sessions.json."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SESSIONS_FILE = PROJECT_DIR / "data" / "sessions.json"
MAX_SESSIONS = 100  # Keep last 100 sessions


def save_session(session_data: dict):
    """Append a session record to sessions.json. Keeps last MAX_SESSIONS."""
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

    sessions = []
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                sessions = json.load(f)
        except (json.JSONDecodeError, IOError):
            sessions = []

    sessions.append(session_data)
    sessions = sessions[-MAX_SESSIONS:]

    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)


def load_sessions(limit: int = 20) -> list:
    """Load recent session history."""
    if not SESSIONS_FILE.exists():
        return []
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            sessions = json.load(f)
        return sessions[-limit:][::-1]  # Most recent first
    except (json.JSONDecodeError, IOError):
        return []


def create_session_record(count: int, mode: str, cooldown: int) -> dict:
    """Create a new session record template."""
    return {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "count": count,
        "mode": mode,
        "cooldown": cooldown,
        "successful": 0,
        "failed": 0,
        "duration_sec": 0,
        "emails": [],
    }


def finish_session_record(record: dict, successful: int, failed: int, emails: list):
    """Finalize a session record with results."""
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    record["successful"] = successful
    record["failed"] = failed
    start = datetime.fromisoformat(record["started_at"])
    end = datetime.fromisoformat(record["finished_at"])
    record["duration_sec"] = round((end - start).total_seconds(), 1)
    record["emails"] = emails
    save_session(record)
