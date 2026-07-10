"""
Dunju AI — Settings Engine
Simple key-value settings storage in SQLite.
Used for General, Appearance, Model, and other app preferences.
"""

from datetime import datetime
from database.db import get_db

DEFAULT_SETTINGS = {
    # General
    "app_name": "Dunju AI Assistant",
    "company_name": "Dunju AI",
    "tagline": "Build. Automate. Scale.",
    "user_name": "",
    "language": "English",
    "theme_color": "#a855f7",
    # AI
    "default_expert": "General",
    "default_model": "dunju-ai:latest",
    "ollama_url": "http://localhost:11434",
    "temperature": "0.7",
    "max_tokens": "2048",
    "streaming": "true",
    # Documents
    "max_upload_mb": "20",
    "auto_ocr": "false",
    "extract_tables": "true",
    "extract_images": "true",
    # Database
    "last_backup": "",
}


def seed_default_settings():
    conn = get_db()
    now = datetime.now().isoformat()
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now)
        )
    conn.commit()
    conn.close()


def get_all_settings() -> dict:
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def get_setting(key: str, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> bool:
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (key, value, now)
    )
    conn.commit()
    conn.close()
    return True


def update_settings(updates: dict) -> bool:
    for key, value in updates.items():
        set_setting(key, str(value))
    return True


def get_db_stats() -> dict:
    """Return database file stats for the About/Database settings tab."""
    import os
    from config.settings import DB_PATH
    size_bytes = os.path.getsize(DB_PATH) if DB_PATH.exists() else 0

    conn = get_db()
    stats = {}
    for table in ["chats", "messages", "experts", "settings"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()["c"]
            stats[table] = count
        except Exception:
            stats[table] = 0

    # Total documents = messages that carry at least one uploaded file
    try:
        docs = conn.execute(
            "SELECT COUNT(*) as c FROM messages "
            "WHERE file_names IS NOT NULL AND file_names != '' AND file_names != '[]'"
        ).fetchone()["c"]
    except Exception:
        docs = 0
    conn.close()

    return {
        "db_path": str(DB_PATH),
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "counts": stats,
        "total_documents": docs,
        "last_backup": get_setting("last_backup", "") or "Never"
    }
