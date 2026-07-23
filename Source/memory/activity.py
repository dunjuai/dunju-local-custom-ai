"""
Dunju AI — Activity Log (v2.14.0)
Lightweight local record of recent app events (uploads, chats, saves, backups…).
Stored in SQLite; capped to the most recent 500 entries.
"""

from datetime import datetime
from database.db import get_db


def log_activity(event: str, detail: str = "") -> None:
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO activity_log (ts, event, detail) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), event, detail or ""),
        )
        conn.execute(
            "DELETE FROM activity_log WHERE id NOT IN "
            "(SELECT id FROM activity_log ORDER BY id DESC LIMIT 500)"
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def recent_activity(limit: int = 50) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT ts, event, detail FROM activity_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_activity() -> bool:
    conn = get_db()
    conn.execute("DELETE FROM activity_log")
    conn.commit()
    conn.close()
    return True
