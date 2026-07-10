"""
Dunju AI — Database Layer
SQLite connection, schema creation, and migrations.
v2.5.1 — Fixed migration: disable FK before table surgery, drop chats_old safely
"""

import sqlite3
from config.settings import DB_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize all tables. Safe to call multiple times (IF NOT EXISTS)."""
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id         TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            skill      TEXT DEFAULT 'General',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id         TEXT NOT NULL,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            display_content TEXT,
            file_names      TEXT,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (chat_id) REFERENCES chats(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS experts (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL UNIQUE,
            emoji             TEXT DEFAULT '🤖',
            color             TEXT DEFAULT '#a855f7',
            system_prompt     TEXT NOT NULL,
            suggested_actions TEXT DEFAULT '[]',
            default_questions TEXT DEFAULT '[]',
            is_builtin        INTEGER DEFAULT 0,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"  Database ready: {DB_PATH}")


def migrate_db():
    """
    Safe migration from v2.4.0 → v2.5.x.

    The core problem: messages.chat_id has a FK → chats(id).
    When we rename chats → chats_old, SQLite silently rewires that FK to
    point at chats_old. Then DROP TABLE chats_old fails with a FK constraint
    error (swallowed silently), leaving the DB half-migrated:
      - chats_old still exists with old rows + the FK target
      - new chats table exists but messages still points at chats_old
      - new chat messages fail to save (FK violation)

    Fix: disable FK enforcement for the duration of the table surgery,
    then rebuild messages with the FK pointing at the correct table.
    """
    # Use a raw connection with FK OFF for the surgery
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # ── 1. Drop leftover tables from a failed previous migration ──
        # Only act (and log) if any of them actually still exist
        existing = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        stale_found = [t for t in ("projects", "knowledge_files", "activity_log") if t in existing]
        if stale_found:
            for stale in stale_found:
                conn.execute(f"DROP TABLE IF EXISTS {stale}")
            conn.commit()
            print(f"  Migration: dropped stale tables ({', '.join(stale_found)})")

        # ── 2. Check if chats_old is still lurking (failed previous run) ──
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        if "chats_old" in tables:
            print("  Migration: chats_old detected — repairing half-migrated database")

            # Disable FK checks — required for table surgery
            conn.execute("PRAGMA foreign_keys = OFF")

            # Recreate messages WITHOUT the stale FK so we can drop chats_old
            conn.execute("""
                CREATE TABLE messages_new (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id         TEXT NOT NULL,
                    role            TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    display_content TEXT,
                    file_names      TEXT,
                    created_at      TEXT NOT NULL
                )
            """)
            conn.execute("""
                INSERT INTO messages_new
                    (id, chat_id, role, content, display_content, file_names, created_at)
                SELECT id, chat_id, role, content, display_content, file_names, created_at
                FROM messages
            """)
            conn.execute("DROP TABLE messages")
            conn.execute("ALTER TABLE messages_new RENAME TO messages")

            # Now safe to drop chats_old
            conn.execute("DROP TABLE IF EXISTS chats_old")
            conn.commit()
            print("  Migration: chats_old dropped, messages table rebuilt")

            # Re-enable FK and add the correct FK back via another rename
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("""
                CREATE TABLE messages_fk (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id         TEXT NOT NULL,
                    role            TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    display_content TEXT,
                    file_names      TEXT,
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES chats(id)
                )
            """)
            conn.execute("""
                INSERT INTO messages_fk
                    (id, chat_id, role, content, display_content, file_names, created_at)
                SELECT id, chat_id, role, content, display_content, file_names, created_at
                FROM messages
            """)
            conn.execute("DROP TABLE messages")
            conn.execute("ALTER TABLE messages_fk RENAME TO messages")
            conn.commit()
            print("  Migration: messages FK reattached to chats")

        # ── 3. Strip project_id from chats if still present ──
        elif "chats" in tables:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(chats)").fetchall()]
            if "project_id" in cols:
                print("  Migration: stripping project_id from chats")
                conn.execute("PRAGMA foreign_keys = OFF")

                conn.execute("""
                    CREATE TABLE chats_new (
                        id         TEXT PRIMARY KEY,
                        title      TEXT NOT NULL,
                        skill      TEXT DEFAULT 'General',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    INSERT INTO chats_new (id, title, skill, created_at, updated_at)
                    SELECT id, title, skill, created_at, updated_at FROM chats
                """)
                conn.execute("DROP TABLE chats")
                conn.execute("ALTER TABLE chats_new RENAME TO chats")
                conn.commit()
                print("  Migration: project_id removed from chats cleanly")

    except Exception as e:
        print(f"  Migration error: {e}")
        conn.rollback()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()